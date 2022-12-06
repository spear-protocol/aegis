from __future__ import absolute_import, unicode_literals
import logging
from django.conf import settings
from celery.utils.log import get_task_logger
from rest_framework import serializers
from operator_api import crypto
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Transfer, ActiveState, MinimumAvailableBalanceMarker, Signature
from enum import Enum
from operator_api.models import ErrorCode

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


def swap_expired(swap, operator_eon_number, checkpoint_created):
    # Incorrect transfer eon number
    if swap.eon_number != operator_eon_number and checkpoint_created:
        logger.error('Swap {} eon mismatch ({}, {})'.format(
            swap.id, swap.eon_number, operator_eon_number))
        return True

    return False


def should_void_swap(
        swap: Transfer,
        wallet_view_context: WalletTransferContext,
        recipient_view_context: WalletTransferContext,
        operator_eon_number: int,
        is_checkpoint_created: bool):
    if not settings.SWAPS_ENABLED:
        logger.error('Swaps disabled. Voiding {}'.format(swap.id))
        return True

    if swap.amount < 1:
        logger.error('Swap {} has less than 1 amount'.format(swap.id))
        return True

    if swap.amount_swapped < 1:
        logger.error('Swap {} has less than 1 amount swapped'.format(swap.id))
        return True

    # Unauthorized transfer
    if swap.sender_active_state is None:
        logger.error('Swap {} no authorization'.format(swap.id))
        return True

    # Invalid signature by sender
    if not swap.sender_active_state.wallet_signature.is_valid():
        logger.error('Swap {} invalid sender signature.'.format(swap.id))
        return True

    # Unreceived transaction
    if swap.recipient_active_state is None:
        logger.error('Swap receipt for {} not provided.'.format(swap.id))
        return True

    # Invalid signature by recipient
    if not swap.recipient_active_state.wallet_signature.is_valid():
        logger.error('Swap {} invalid receipt signature.'.format(swap.id))
        return True

    # Ensure log consistency
    can_append_to_sender_log = wallet_view_context.can_append_transfer()
    if can_append_to_sender_log is not True:
        logger.error('Sender: {}'.format(can_append_to_sender_log))
        return True
    can_append_to_recipient_log = recipient_view_context.can_append_transfer()
    if can_append_to_recipient_log is not True:
        logger.error('Recipient: {}'.format(can_append_to_recipient_log))
        return True

    # Skip consistency checks since they were done at least once before.
    if swap.appended:
        return False

    # Overspending
    sender_funds_remaining = wallet_view_context.loosely_available_funds_at_eon(
        eon_number=swap.eon_number,
        current_eon_number=operator_eon_number,
        is_checkpoint_created=is_checkpoint_created,
        only_appended=True)

    # sender remaining funds should be more than remaining amount in order
    matched_out, matched_in = swap.matched_amounts(all_eons=True)
    if sender_funds_remaining < swap.amount - matched_out:
        logger.error('Swap {} overspending.'.format(swap.id))
        return True

    # Prevent future overdrawing
    # if swap.sender_balance_marker.amount > sender_funds_remaining - swap.amount:
    if swap.sender_balance_marker.amount != 0:
        logger.error('Swap {} invalid concise marker balance.'.format(swap.id))
        return True

    concise_balance_marker = MinimumAvailableBalanceMarker(
        wallet=swap.wallet,
        eon_number=swap.eon_number,
        amount=swap.sender_balance_marker.amount)
    concise_balance_marker_checksum = crypto.hex_value(
        concise_balance_marker.checksum())
    if swap.sender_balance_marker.signature.checksum != concise_balance_marker_checksum:
        logger.error('Swap {} invalid concise marker checksum for {}.'.format(
            swap.id, swap.sender_balance_marker.amount))
        return True

    highest_spendings, highest_gains = wallet_view_context.off_chain_actively_sent_received_amounts(
        eon_number=swap.eon_number,
        only_appended=True)

    # if this is a multi eon swap
    if Transfer.objects.filter(eon_number=swap.eon_number-1, tx_id=swap.tx_id).exists():
        # set balances to initial fixed balances stored in transfer eon state
        sender_starting_balance = swap.sender_starting_balance
        recipient_starting_balance = swap.recipient_starting_balance

        # make sure this eon's starting balance is exactly  the initial stored balance
        # when matched amount is taken into consideration for both sender and receiver
        if wallet_view_context.starting_balance_in_eon(swap.eon_number) != sender_starting_balance - matched_out:
            logger.error('Swap {} invalid sender starting balance of future state {} != {} - {}.'.format(
                swap.id,
                wallet_view_context.starting_balance_in_eon(swap.eon_number),
                sender_starting_balance,
                matched_out))
        if recipient_view_context.starting_balance_in_eon(swap.eon_number) != recipient_starting_balance + matched_in:
            logger.error('Swap {} invalid recipient starting balance of future state {} != {} + {}.'.format(
                swap.id,
                recipient_view_context.starting_balance_in_eon(
                    swap.eon_number),
                recipient_starting_balance,
                matched_out))
        assert(wallet_view_context.starting_balance_in_eon(
            swap.eon_number) == sender_starting_balance - matched_out)
        assert(recipient_view_context.starting_balance_in_eon(
            swap.eon_number) == recipient_starting_balance + matched_in)
    else:
        sender_starting_balance = int(
            wallet_view_context.starting_balance_in_eon(swap.eon_number))
        recipient_starting_balance = int(
            recipient_view_context.starting_balance_in_eon(swap.eon_number))

    # Debit Authorization
    tx_set_tree = wallet_view_context.optimized_authorized_transfers_tree(
        only_appended=True, starting_balance=sender_starting_balance)
    tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
    transfer_index = tx_set_tree.merkle_tree_nonce_map.get(swap.nonce)
    transfer_proof = tx_set_tree.proof(transfer_index)

    highest_spendings, highest_gains = wallet_view_context.off_chain_actively_sent_received_amounts(
        eon_number=swap.eon_number,
        only_appended=True)
    debiting_active_state = ActiveState(
        wallet=swap.wallet,
        updated_spendings=highest_spendings + swap.amount,
        updated_gains=highest_gains,
        tx_set_hash=tx_set_hash,
        tx_set_proof_hashes=transfer_proof,
        tx_set_index=transfer_index,
        eon_number=swap.eon_number)

    debiting_active_state_checksum = crypto.hex_value(
        debiting_active_state.checksum())
    if swap.sender_active_state.wallet_signature.checksum != debiting_active_state_checksum:
        logger.error(
            'Swap {} invalid debit active state checksum.'.format(swap.id))
        return True

    # Credit Authorization
    tx_set_tree = recipient_view_context.optimized_authorized_transfers_tree(
        only_appended=True, starting_balance=recipient_starting_balance)
    tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
    transfer_index = tx_set_tree.merkle_tree_nonce_map.get(swap.nonce)
    transfer_proof = tx_set_tree.proof(transfer_index)

    highest_spendings, highest_gains = recipient_view_context.off_chain_actively_sent_received_amounts(
        eon_number=swap.eon_number,
        only_appended=True)

    crediting_active_state = ActiveState(
        wallet=swap.recipient,
        updated_spendings=highest_spendings,
        updated_gains=highest_gains,
        tx_set_hash=tx_set_hash,
        tx_set_proof_hashes=transfer_proof,
        tx_set_index=transfer_index,
        eon_number=swap.eon_number)

    crediting_active_state_checksum = crypto.hex_value(
        crediting_active_state.checksum())
    if swap.recipient_active_state.wallet_signature.checksum != crediting_active_state_checksum:
        logger.error(
            'Swap {} invalid credit active state checksum.'.format(swap.id))
        return True

    # Finality Authorization
    swap.complete = True
    tx_set_tree = recipient_view_context.optimized_authorized_transfers_tree(
        only_appended=True, starting_balance=recipient_starting_balance)
    swap.complete = False
    tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
    transfer_index = tx_set_tree.merkle_tree_nonce_map.get(swap.nonce)
    transfer_proof = tx_set_tree.proof(transfer_index)

    recipient_fulfillment_active_state = ActiveState(
        wallet=swap.recipient,
        updated_spendings=highest_spendings,
        updated_gains=highest_gains + swap.amount_swapped,
        tx_set_hash=tx_set_hash,
        tx_set_proof_hashes=transfer_proof,
        tx_set_index=transfer_index,
        eon_number=swap.eon_number)

    recipient_fulfillment_active_state_checksum = crypto.hex_value(
        recipient_fulfillment_active_state.checksum())
    if swap.recipient_fulfillment_active_state.wallet_signature.checksum != recipient_fulfillment_active_state_checksum:
        logger.error(
            'Swap {} invalid finalization active state checksum.'.format(swap.id))
        return True

    return False


class SignatureType(Enum):
    DEBIT = 1
    CREDIT = 2
    FULFILLMENT = 3


# helper function to check signature validity, returns active state and cache
# signature_type is 1 for debit state, 2 for credit state and 3 for fulfillment state
def check_active_state_signature(swap, wallet, active_state_signature_data, is_future_state, starting_balance, highest_spendings, highest_gains, signature_type=None):
    wallet_view_context = WalletTransferContext(wallet=wallet, transfer=swap)

    # fulfillment active state
    if signature_type == SignatureType.FULFILLMENT:
        swap.processed, swap.complete = True, True

    if is_future_state:
        # done for all future eons
        # assumes this is the only TX in set
        tx_set_tree = WalletTransferContext.optimized_authorized_transfers_tree_from_list([
            swap.shorthand(wallet_view_context, is_last_transfer=True,
                           starting_balance=starting_balance)
        ])
    else:
        # done once for current eon
        tx_set_tree = wallet_view_context.optimized_authorized_transfers_tree()

    # fulfillment active state
    if signature_type == SignatureType.FULFILLMENT:
        swap.processed, swap.complete = False, False

    tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
    transfer_index = tx_set_tree.merkle_tree_nonce_map.get(swap.nonce)
    transfer_proof = tx_set_tree.proof(transfer_index)

    # debit active state
    if signature_type == SignatureType.DEBIT:
        updated_spendings = highest_spendings + swap.amount
        updated_gains = highest_gains
        state_name = "Debit"
    # credit active state
    elif signature_type == SignatureType.CREDIT:
        updated_spendings = highest_spendings
        updated_gains = highest_gains
        state_name = "Credit"
    # fulfillment active state
    elif signature_type == SignatureType.FULFILLMENT:
        updated_spendings = highest_spendings
        updated_gains = highest_gains + swap.amount_swapped
        state_name = "Fulfillment"

    active_state = ActiveState(
        wallet=wallet,
        updated_spendings=updated_spendings,
        updated_gains=updated_gains,
        tx_set_hash=tx_set_hash,
        tx_set_proof_hashes=transfer_proof,
        tx_set_index=transfer_index,
        eon_number=swap.eon_number)

    active_state_checksum = crypto.hex_value(active_state.checksum())
    active_state_signature = Signature(
        wallet=wallet,
        checksum=active_state_checksum,
        value=active_state_signature_data.get('value'))
    if not active_state_signature.is_valid():
        error_code = None
        if signature_type == SignatureType.CREDIT:
            error_code = ErrorCode.INVALID_FUTURE_CREDIT_SIGNATURE if is_future_state else ErrorCode.INVALID_CREDIT_SIGNATURE
        elif signature_type == SignatureType.DEBIT:
            error_code = ErrorCode.INVALID_FUTURE_DEBIT_SIGNATURE if is_future_state else ErrorCode.INVALID_DEBIT_SIGNATURE
        elif signature_type == SignatureType.FULFILLMENT:
            error_code = ErrorCode.INVALID_FUTURE_CREDIT_FULFILLMENT_SIGNATURE if is_future_state else ErrorCode.INVALID_CREDIT_FULFILLMENT_SIGNATURE

        raise serializers.ValidationError(
            'Active state signature failed for eon {}'.format(swap.eon_number), code=error_code)

    return active_state, active_state_signature, transfer_index, tx_set_tree.merkle_cache_stacks()
