from __future__ import absolute_import, unicode_literals

import logging

from django.conf import settings
from django.db import transaction, IntegrityError
from celery import shared_task
from celery.utils.log import get_task_logger

from contractor.interfaces import LocalViewInterface
from operator_api.crypto import hex_value
from operator_api.email import send_admin_email
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Transfer, ActiveState, RootCommitment, MinimumAvailableBalanceMarker
from operator_api.celery import operator_celery

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def process_passive_transfer_finalizations():
    raise NotImplemented()  # TODO Implement

    logger.info('Processing passive transfers')

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    latest_eon_number = LocalViewInterface.latest().eon_number()

    # This lock is required because the ledger will be mutated as the transfers are processed
    with RootCommitment.global_lock():
        logger.info('Start')
        process_passive_transfer_finalizations_for_eon(latest_eon_number)


def process_passive_transfer_finalizations_for_eon(operator_eon_number):
    checkpoint_created = RootCommitment.objects.filter(
        eon_number=operator_eon_number).exists()
    with transaction.atomic():
        transfers = Transfer.objects\
            .filter(processed=False, swap=False, passive=True)\
            .select_for_update()\
            .order_by('eon_number', 'id')

        for transfer in transfers:
            try:
                with transaction.atomic():
                    process_passive_transfer(
                        transfer, operator_eon_number, checkpoint_created)
            except IntegrityError as e:
                send_admin_email(
                    subject='Transfer Integrity Error',
                    content='{}'.format(e))
                logger.error(e)


def should_void_transfer(transfer, wallet_view_context: WalletTransferContext, recipient_view_context: WalletTransferContext, operator_eon_number, is_checkpoint_created):
    if transfer.eon_number != operator_eon_number and is_checkpoint_created:
        logger.error('Transfer {} eon mismatch ({}, {})'.format(
            transfer.id, transfer.eon_number, operator_eon_number))
        return True

    if transfer.amount < 0:
        logger.error('Transfer {} has negative amount'.format(transfer.id))
        return True

    # Unauthorized transfer
    if transfer.sender_active_state is None:
        logger.error('Transfer {} no authorization'.format(transfer.id))
        return True

    # Invalid signature by sender
    if not transfer.sender_active_state.wallet_signature.is_valid():
        logger.error(
            'Transfer {} invalid sender signature.'.format(transfer.id))
        return True

    # Ensure sender log consistency
    can_append_to_sender_log = wallet_view_context.can_append_transfer()
    if can_append_to_sender_log is not True:
        logger.error('Sender: {}'.format(can_append_to_sender_log))
        return True

    # Ensure recipient log consistency
    can_append_to_recipient_log = recipient_view_context.can_append_transfer()
    if can_append_to_recipient_log is not True:
        logger.error('Recipient: {}'.format(can_append_to_recipient_log))
        return True

    # Ensure transfer consistency
    can_spend, currently_available_funds = wallet_view_context.can_send_transfer(
        current_eon_number=operator_eon_number,
        using_only_appended_funds=True)
    if can_spend is not True:
        logger.error(can_spend)
        return True

    last_sent_transfer = wallet_view_context.last_appended_outgoing_active_transfer(
        operator_eon_number)
    last_sent_transfer_active_state = WalletTransferContext.appropriate_transfer_active_state(
        transfer=last_sent_transfer,
        is_outgoing=True)

    previous_spendings = last_sent_transfer_active_state.updated_spendings if last_sent_transfer else 0
    updated_spendings = transfer.sender_active_state.updated_spendings

    # Incorrect updated spendings
    if last_sent_transfer:
        if updated_spendings != previous_spendings + transfer.amount:
            logger.error('Transfer {} invalid updated spendings. Expected {}, found {}.'.format(
                transfer.id, previous_spendings + transfer.amount, updated_spendings))
            return True
    elif updated_spendings != transfer.amount:
        logger.error('Transfer {} invalid initial spendings. Expected {}, found {}.'.format(
            transfer.id, transfer.amount, updated_spendings))
        return True

    # Incorrect transfer position
    last_passively_received = recipient_view_context.last_appended_incoming_passive_transfer(
        operator_eon_number)
    if last_passively_received:
        if transfer.position != last_passively_received.position + last_passively_received.amount:
            logger.error('Transfer {} invalid offset. Expected {}, found {}.'.format(
                transfer.id, last_passively_received.position + last_passively_received.amount, transfer.position))
            return True
    elif transfer.position != 0:
        logger.error('Transfer {} invalid offset. Expected {}, found {}.'.format(
            transfer.id, 0, transfer.position))
        return True

    if transfer.sender_balance_marker.amount > currently_available_funds - transfer.amount:
        logger.error(
            'Transfer {} invalid concise marker balance.'.format(transfer.id))
        return True

    concise_balance_marker = MinimumAvailableBalanceMarker(
        wallet=transfer.wallet,
        eon_number=transfer.eon_number,
        amount=transfer.sender_balance_marker.amount)
    concise_balance_marker_checksum = hex_value(
        concise_balance_marker.checksum())
    if transfer.sender_balance_marker.signature.checksum != concise_balance_marker_checksum:
        logger.error(
            'Transfer {} invalid concise marker checksum.'.format(transfer.id))
        return True

    return False


def process_passive_transfer(transfer, operator_eon_number, checkpoint_created):
    if transfer.wallet == transfer.recipient:
        logger.info('Voiding self transfer.')
        transfer.close(voided=True)
        return

    with transfer.lock(auto_renewal=True), transfer.wallet.lock(auto_renewal=True), transfer.recipient.lock(auto_renewal=True):
        wallet_view_context = WalletTransferContext(
            wallet=transfer.wallet, transfer=transfer)
        recipient_view_context = WalletTransferContext(
            wallet=transfer.recipient, transfer=transfer)

        if should_void_transfer(transfer, wallet_view_context, recipient_view_context, operator_eon_number, checkpoint_created):
            logger.info('Voiding transfer.')
            transfer.close(voided=True)
            return

        # Invalid active state update
        tx_set_list = wallet_view_context.authorized_transfers_list_shorthand(
            only_appended=True,
            force_append=True,
            last_transfer_is_finalized=False)
        tx_set_tree = WalletTransferContext.authorized_transfers_tree_from_list(
            tx_set_list)
        tx_set_hash = hex_value(tx_set_tree.root_hash())
        highest_spendings, highest_gains = wallet_view_context.off_chain_actively_sent_received_amounts(
            eon_number=transfer.eon_number,
            only_appended=True)

        active_state = ActiveState(
            wallet=transfer.wallet,
            updated_spendings=transfer.sender_active_state.updated_spendings,
            updated_gains=highest_gains,
            tx_set_hash=tx_set_hash,
            eon_number=transfer.eon_number)

        raw_checksum = active_state.checksum()
        encoded_checksum = hex_value(raw_checksum)

        wallet_active_state = transfer.sender_active_state

        if wallet_active_state.wallet_signature.checksum != encoded_checksum:
            logger.error('Transfer {} invalid sender active state checksum for {}'.format(
                transfer.id, transfer.wallet.address))
            transfer.close(voided=True)
            return

        try:
            wallet_active_state.operator_signature = wallet_active_state.sign_active_state(
                settings.HUB_OWNER_ACCOUNT_ADDRESS,
                settings.HUB_OWNER_ACCOUNT_KEY)
        except LookupError as e:
            logger.error(e)
            return

        transfer.sender_active_state.save()

        transfer.close(
            complete=True,
            appended=True)

        operator_celery.send_task(
            'auditor.tasks.on_transfer_confirmation', args=[transfer.id])

        logger.info('Transfer {} processed.'.format(transfer.id))
