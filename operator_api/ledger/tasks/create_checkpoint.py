import logging
from django.conf import settings
from django.db import transaction
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import Sum, Q
from eth_utils import remove_0x_prefix
from contractor.interfaces import LocalViewInterface, NOCUSTContractInterface
from operator_api.crypto import hex_value
from operator_api.email import send_admin_email
from operator_api.merkle_tree import MerkleTree
from operator_api.token_merkle_tree import TokenMerkleTree
from operator_api.tx_merkle_tree import TransactionMerkleTree
from operator_api.passive_delivery_merkle_tree import PassiveDeliveryMerkleTree
from operator_api.util import ZERO_CHECKSUM
from operator_api.models import BulkCreateManager
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import ExclusiveBalanceAllotment, TokenCommitment, Wallet, Transfer, WithdrawalRequest, RootCommitment, Token
from operator_api.celery import operator_celery
from operator_api.decorators import notification_on_error

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def create_checkpoint():

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    latest = LocalViewInterface.latest()
    latest_eon_number, latest_sub_block = latest.eon_number_and_sub_block()
    blocks_for_creation = LocalViewInterface.blocks_for_creation()

    confirmed_eon_number, confirmed_sub_block = LocalViewInterface.confirmed(
    ).eon_number_and_sub_block()
    if confirmed_eon_number < latest_eon_number:
        return
    if latest_sub_block < blocks_for_creation:
        return

    with RootCommitment.global_lock():
        new_checkpoint = create_checkpoint_for_eon(latest_eon_number, latest.block)
        if new_checkpoint:
            operator_celery.send_task('auditor.tasks.broadcast_wallet_data')


def create_checkpoint_for_eon(eon_number, latest_block_number):
    if RootCommitment.objects.filter(eon_number=eon_number).count() > 0:
        return False

    if eon_number > 1:
        last_eon_number = eon_number - 1
        last_eon = LocalViewInterface.confirmed(eon_number=last_eon_number)
        if not last_eon:
            logger.error(
                'Missing confirmed contract state for eon {}.'.format(last_eon_number))
            send_admin_email(
                subject='Soft Checkpoint Error: Missing Contract State',
                content='Missing confirmed contract state for previous eon {}. We may not be in sync with the blockchain!'.format(last_eon_number))
            return False

        last_confirmed_eon_number, last_confirmed_sub_block = last_eon.eon_number_and_sub_block()
        if last_confirmed_eon_number != last_eon_number:
            logger.error(
                'Attempted to use confirmed state for eon {}. Expected {}.'.format(last_confirmed_eon_number,
                                                                                   last_eon_number))
            send_admin_email(
                subject='Soft Checkpoint Error: Wrong last eon #',
                content='Need to sync chain! Attempted to use confirmed state for eon {}. Expected {}!'
                .format(last_confirmed_eon_number,
                        last_eon_number))
            return False
        last_sub_block_number = LocalViewInterface.get_contract_parameters().blocks_per_eon - 1
        if last_confirmed_sub_block != last_sub_block_number:
            logger.error(
                'Attempted to use confirmed state for sub block {}. Expected {}.'.format(last_confirmed_sub_block,
                                                                                         last_sub_block_number))
            send_admin_email(
                subject='Soft Checkpoint Error: Wrong last Sub block #',
                content='Need to sync chain! Attempted to use confirmed state for sub block {}. Expected {}.'
                .format(last_confirmed_sub_block,
                        last_sub_block_number))
            return False

    # commitment write read lock makes sure transaction confirmation will not mutate ledger while checkpoint is being created
    with transaction.atomic(), RootCommitment.read_write_lock(suffix=eon_number-1, is_write=True, auto_renewal=True):
        # TODO parallelism
        token_commitments = [create_token_commitment_for_eon(token, eon_number) for token in
                             Token.objects.all().order_by('trail')]

        root_commitment = create_root_commitment_for_eon(
            token_commitments, eon_number, latest_block_number)

        NOCUSTContractInterface().queue_submit_checkpoint(root_commitment)

    return True


def create_root_commitment_for_eon(token_commitments: [TokenCommitment], eon_number, latest_block_number):
    token_commitment_leaves = [commitment.shorthand()
                               for commitment in token_commitments]
    token_merkle_tree = TokenMerkleTree(token_commitment_leaves)
    token_merkle_tree_root = hex_value(token_merkle_tree.root_hash())

    previous_eon_basis = ZERO_CHECKSUM
    if eon_number > 1:
        local_block = LocalViewInterface.confirmed(eon_number - 1)
        print(local_block.__dict__)
        print(local_block.eon_number())
        previous_eon_basis = local_block.basis

    root_commitment = RootCommitment.objects.create(
        eon_number=eon_number,
        basis=previous_eon_basis,
        merkle_root=token_merkle_tree_root,
        block=latest_block_number)

    for token_commitment in token_commitments:
        token_commitment.root_commitment = root_commitment
        token_commitment.membership_hashes = token_merkle_tree.proof(
            token_commitment.token.trail)
        token_commitment.save()

    return root_commitment


def create_token_commitment_for_eon(token: Token, eon_number):
    logger.info('Creating Token Commitment for {} at {}'.format(
        token.address, eon_number))
    last_eon_number = eon_number - 1

    with transaction.atomic():
        wallets = Wallet.objects\
            .filter(
                token=token,
                registration_operator_authorization__isnull=False,
                trail_identifier__isnull=False)\
            .order_by('trail_identifier')

        new_balances = []
        left, right = 0, 0

        for wallet in wallets:
            with wallet.lock(auto_renewal=True):
                wallet_transfer_context = WalletTransferContext(
                    wallet=wallet, transfer=None)

                last_transfer, last_transfer_is_outgoing = wallet_transfer_context.last_appended_active_transfer(
                    eon_number=last_eon_number)

                last_transfer_active_state = None
                if last_transfer is not None and last_transfer.is_open_swap():
                    last_transfer.retire_swap()

                if last_transfer is not None:
                    last_transfer_active_state = WalletTransferContext.appropriate_transfer_active_state(
                        transfer=last_transfer,
                        is_outgoing=last_transfer_is_outgoing)

                available_funds = wallet_transfer_context.available_funds_at_eon(
                    eon_number=last_eon_number,
                    only_appended=True)

                right = left + available_funds
                assert right >= left, 'Wallet {} Token {} Balance {}'.format(
                    wallet.address, token.address, available_funds)

                passive_checksum, passive_amount, passive_marker = wallet_transfer_context.get_passive_values(
                    eon_number=last_eon_number)

                new_balances.append({
                    'contract': settings.HUB_LQD_CONTRACT_ADDRESS,
                    'token': token.address,
                    'wallet': wallet.address,
                    'left': left,
                    'right': right,
                    'active_state_checksum': last_transfer_active_state.checksum() if last_transfer_active_state is not None else b'\0'*32,
                    'active_state': last_transfer_active_state,
                    'passive_checksum': passive_checksum,
                    'passive_amount': passive_amount,
                    'passive_marker': passive_marker,
                })
                left = right

                last_incoming_passive_transfer = wallet_transfer_context.last_appended_incoming_passive_transfer(
                    eon_number=last_eon_number)
                if last_incoming_passive_transfer:
                    wallet_transfer_context = WalletTransferContext(
                        wallet=wallet, transfer=last_incoming_passive_transfer)

                    passive_eon_transfers_list = wallet_transfer_context.incoming_passive_transfers_list(
                        only_appended=True,
                        force_append=False)
                    passive_transfers_merkle_tree = wallet_transfer_context.incoming_passive_transfers_tree(
                        only_appended=True,
                        force_append=False)

                    for index, incoming_passive_transfer in enumerate(passive_eon_transfers_list):

                        final_transfer_index = index
                        final_transfer_membership_proof = passive_transfers_merkle_tree.proof(
                            final_transfer_index)
                        final_transfer_membership_proof_chain = final_transfer_membership_proof.get(
                            "chain")
                        final_transfer_membership_proof_values = final_transfer_membership_proof.get(
                            "values")

                        assert incoming_passive_transfer.final_receipt_hashes is None
                        assert incoming_passive_transfer.final_receipt_index is None
                        assert incoming_passive_transfer.final_receipt_values is None

                        incoming_passive_transfer.final_receipt_hashes = final_transfer_membership_proof_chain
                        incoming_passive_transfer.final_receipt_index = final_transfer_index
                        incoming_passive_transfer.final_receipt_values = final_transfer_membership_proof_values

                        incoming_passive_transfer.save()

                if last_transfer_active_state is None:
                    continue

                wallet_transfer_context = WalletTransferContext(
                    wallet=wallet, transfer=last_transfer)
                starting_balance = int(
                    wallet_transfer_context.starting_balance_in_eon(last_eon_number))

                # if last active transfer is a multi eon swap
                # starting balance included in every tx checksum should be set to the cached starting balance
                # this way checkpoint state will match signed active state
                if last_transfer.is_swap() and not last_transfer.cancelled:
                    if Transfer.objects.filter(eon_number=last_transfer.eon_number-1, tx_id=last_transfer.tx_id).exists():
                        matched_out, matched_in = last_transfer.matched_amounts(
                            all_eons=True)
                        current_matched_out, current_matched_in = last_transfer.matched_amounts(
                            all_eons=False)
                        if last_transfer_is_outgoing:
                            sender_starting_balance = last_transfer.sender_starting_balance

                            # current eon's starting balance should be equal to
                            # cached starting balance - committed matched out amount in past rounds
                            assert(starting_balance == sender_starting_balance -
                                   matched_out + current_matched_out)
                            starting_balance = sender_starting_balance
                        else:
                            recipient_starting_balance = last_transfer.recipient_starting_balance

                            # current eon's starting balance should be equal to
                            # cached starting balance + committed matched in amount in past rounds
                            assert(
                                starting_balance == recipient_starting_balance + matched_in - current_matched_in)
                            starting_balance = recipient_starting_balance

                confirmed_eon_transfers_list = wallet_transfer_context.authorized_transfers_list(
                    only_appended=True,
                    force_append=False)
                confirmed_eon_transfers_list_shorthand = wallet_transfer_context.authorized_transfers_list_shorthand(
                    only_appended=True,
                    force_append=False,
                    last_transfer_is_finalized=False,
                    starting_balance=starting_balance)
                transaction_merkle_tree = TransactionMerkleTree(
                    confirmed_eon_transfers_list_shorthand)
                transaction_merkle_tree_root = hex_value(
                    transaction_merkle_tree.root_hash())

                assert transaction_merkle_tree_root == last_transfer_active_state.tx_set_hash,\
                    '{}/{}'.format(transaction_merkle_tree_root,
                                   last_transfer_active_state.tx_set_hash)

                for confirmed_incoming_transfer in confirmed_eon_transfers_list:
                    if confirmed_incoming_transfer.recipient != wallet:
                        continue

                    final_transfer_index = transaction_merkle_tree.merkle_tree_nonce_map.get(
                        confirmed_incoming_transfer.nonce)
                    final_transfer_membership_proof_chain = transaction_merkle_tree.proof(
                        final_transfer_index)

                    assert confirmed_incoming_transfer.final_receipt_hashes is None
                    assert confirmed_incoming_transfer.final_receipt_index is None

                    confirmed_incoming_transfer.final_receipt_hashes = final_transfer_membership_proof_chain
                    confirmed_incoming_transfer.final_receipt_index = final_transfer_index

                    confirmed_incoming_transfer.save()

        managed_funds = 0
        if eon_number > 1:
            last_eon = LocalViewInterface.confirmed(eon_number=last_eon_number)
            pending_withdrawals_until_last_eon = \
                WithdrawalRequest.objects\
                .filter(wallet__token=token, eon_number__lte=last_eon_number, slashed=False)\
                .filter(Q(withdrawal__isnull=True) | Q(withdrawal__block__gt=last_eon.block))

            if not pending_withdrawals_until_last_eon.exists():
                last_eon_pending_withdrawals = 0
            else:
                last_eon_pending_withdrawals = pending_withdrawals_until_last_eon\
                    .aggregate(Sum('amount')) \
                    .get('amount__sum')

            total_token_balance = last_eon.contractledgerstate_set.get(
                token=token).total_balance
            managed_funds = total_token_balance - last_eon_pending_withdrawals

        if right < managed_funds:
            logger.warning('UNCLAIMED FUNDS: {} in {}'.format(
                managed_funds - right, token.address))
            send_admin_email(
                subject='Soft TokenCommitment Warning: Extra funds',
                content='There are some additional funds in the balance pool that belong to no one: {} of {}'
                .format(managed_funds - right, token.address))
            altered_balances = new_balances + [{
                'contract': settings.HUB_LQD_CONTRACT_ADDRESS,
                'token': token.address,
                'wallet': settings.HUB_OWNER_ACCOUNT_ADDRESS,
                'left': left,
                'right': managed_funds,
                'active_state_checksum': b'\0'*32,
                'active_state': None,
                'passive_checksum': b'\0'*32,
                'passive_amount': 0,
                'passive_marker': 0,
            }]
            new_merkle_tree = MerkleTree(altered_balances, managed_funds)
            right = managed_funds
        else:
            if right > managed_funds:
                logger.error('OVERCLAIMING FUNDS!! {} > {} in {}'.format(
                    right, managed_funds, token.address))
                send_admin_email(
                    subject='HARD Checkpoint Error: OVERCLAIMING!',
                    content='OVERCLAIMING FUNDS!! {} > {} in {}'.format(right, managed_funds, token.address))
            new_merkle_tree = MerkleTree(new_balances, right)

        bulk_manager = BulkCreateManager(chunk_size=500)
        for index, balance in enumerate(new_balances):
            if not balance.get('wallet') or balance.get('wallet') == '0x0000000000000000000000000000000000000000':
                continue

            merkle_proof = new_merkle_tree.proof(index)

            wallet = Wallet.objects.get(
                token=token,
                address=remove_0x_prefix(balance.get('wallet')))

            # TODO verify validity through RPC prior to insertion

            assert(wallet.trail_identifier == index)

            # create records in batches
            bulk_manager.add(
                ExclusiveBalanceAllotment(
                    wallet=wallet,
                    eon_number=eon_number,
                    left=balance.get('left'),
                    right=balance.get('right'),
                    merkle_proof_hashes=merkle_proof.get('chain'),
                    merkle_proof_values=merkle_proof.get('values'),
                    merkle_proof_trail=index,
                    active_state=balance.get('active_state')
                )
            )
        # make sure remaining batch is added
        bulk_manager.done()

        token_commitment = TokenCommitment.objects.create(
            token=token,
            merkle_root=hex_value(new_merkle_tree.root_hash()),
            upper_bound=right)

        return token_commitment
