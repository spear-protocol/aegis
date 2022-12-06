import logging
import traceback
from operator_api.decorators import notification_on_error
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from contractor.interfaces import NOCUSTContractInterface
from operator_api.email import send_admin_email
from operator_api.merkle_tree import calculate_merkle_proof
from operator_api.tx_merkle_tree import TransactionMerkleTree
from operator_api.util import long_string_to_list, csf_to_list
from operator_api import crypto
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Challenge, TokenCommitment, ExclusiveBalanceAllotment, Transfer, RootCommitment, TokenPair, Deposit
from eth_utils import to_checksum_address

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def respond_to_challenges():
    contract_interface = NOCUSTContractInterface()

    contract_interface.get_current_eon_number()

    latest_root_commitment = RootCommitment.objects\
        .all()\
        .order_by('eon_number')\
        .last()

    if latest_root_commitment is None:
        return

    with Challenge.global_lock():
        challenges = Challenge.objects\
            .filter(rebuted=False, eon_number__lte=latest_root_commitment.eon_number)\
            .order_by('block')
        for challenge in challenges:
            token = challenge.wallet.token
            challenge_entry_token = token.address

            if challenge.wallet.token != challenge.recipient.token:
                try:
                    tp = TokenPair.objects.get(
                        token_from=challenge.wallet.token, token_to=challenge.recipient.token)
                except TokenPair.DoesNotExist:
                    logger.warning(
                        "Skipping challenge for {}. token pair not found!".format(challenge.wallet.address))
                    continue

                token = challenge.recipient.token
                challenge_entry_token = to_checksum_address(tp.conduit)

            challenge_entry = contract_interface.get_challenge_record(
                token_address=challenge_entry_token,
                recipient=challenge.recipient.address,
                sender=challenge.wallet.address)

            if not challenge_entry.challengeStage:
                logger.warning(
                    "Skipping answered challenge for {}. Where is the answer tx_id?".format(challenge.wallet.address))
                continue

            try:
                recipient_balance = ExclusiveBalanceAllotment.objects.get(
                    wallet=challenge.recipient,
                    eon_number=challenge.eon_number)
            except ExclusiveBalanceAllotment.DoesNotExist:
                logger.error("Could not find balance for {} at eon {}.".format(
                    challenge.wallet.address, challenge.eon_number))
                send_admin_email(
                    subject='DISPUTE! NO BALANCE!',
                    content='{}'.format(challenge.wallet.address))
                return

            token_commitment = TokenCommitment.objects.get(
                token=token,
                root_commitment__eon_number=challenge.eon_number)

            # state update challenge
            if challenge.wallet.token == challenge.recipient.token and challenge.wallet.address == challenge.recipient.address:

                v_0, r_0, s_0 = recipient_balance.wallet_v_r_s()
                v_1, r_1, s_1 = recipient_balance.operator_v_r_s()

                recipient_transfer_context = WalletTransferContext(
                    wallet=challenge.recipient, transfer=None)

                passive_checksum, passive_amount, passive_marker = recipient_transfer_context.get_passive_values(
                    eon_number=challenge_entry.initialStateEon)

                logger.info("Answering challenge for {} with balance {}.".format(
                    challenge.wallet.address, recipient_balance.amount()))
                logger.info("{}{}{}, {}{}{}".format(
                    v_0, r_0, s_0, v_1, r_1, s_1))
                send_admin_email(
                    subject='DISPUTE! Sate Update.',
                    content='{}'.format(challenge.wallet.address))

                # TODO signal critical failure if this does not succeed!
                transaction = contract_interface.queue_answer_state_update_challenge(
                    challenge=challenge,
                    allotment_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                     long_string_to_list(recipient_balance.merkle_proof_hashes, 64)],
                    membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                      long_string_to_list(token_commitment.membership_hashes, 64)],
                    values=csf_to_list(
                        recipient_balance.merkle_proof_values, int),
                    l_r=[int(recipient_balance.left),
                         int(recipient_balance.right)],
                    tx_set_root=crypto.zfill(crypto.decode_hex(
                        recipient_balance.transaction_set_root())),
                    deltas=[d for d in recipient_balance.deltas()],
                    r=[crypto.uint256(r_0), crypto.uint256(r_1)],
                    s=[crypto.uint256(s_0), crypto.uint256(s_1)],
                    v=[v_0, v_1],
                    passive_checksum=passive_checksum,
                    passive_amount=passive_amount,
                    passive_marker=passive_marker)

            # transfer challenge
            elif challenge.wallet.token == challenge.recipient.token and challenge.wallet.address != challenge.recipient.address:
                try:
                    transfer = Transfer.objects.get(
                        recipient=challenge.recipient,
                        eon_number=challenge_entry.initialStateEon,
                        nonce=challenge_entry.deliveredTxNonce)
                except Transfer.DoesNotExist:
                    logger.error(
                        "Could not find transfer for {} at eon {} with nonce {}."
                        .format(challenge.recipient.address, challenge.eon_number, challenge_entry.deliveredTxNonce))
                    send_admin_email(
                        subject='DISPUTE! NO TRANSFER!',
                        content="Could not find transfer for {} at eon {} with nonce {}."
                        .format(challenge.recipient.address, challenge.eon_number, challenge_entry.deliveredTxNonce))
                    return

                recipient_transfer_context = WalletTransferContext(
                    wallet=challenge.recipient, transfer=None)

                transfers_list_nonce_index_map = {}
                transfers_list = recipient_transfer_context.authorized_transfers_list_shorthand(
                    only_appended=True,
                    force_append=False,
                    eon_number=challenge_entry.initialStateEon,
                    last_transfer_is_finalized=False,
                    index_map=transfers_list_nonce_index_map)

                transfer_tree = TransactionMerkleTree(transfers_list)
                transfer_index = transfers_list_nonce_index_map.get(
                    transfer.nonce)
                transfer_node = transfer_tree.merkle_tree_leaf_map.get(
                    transfer_index)
                transfer_proof = [node.get('hash') for node in calculate_merkle_proof(
                    transfer_index, transfer_node)]

                passive_checksum, passive_amount, passive_marker = recipient_transfer_context.get_passive_values(
                    eon_number=challenge_entry.initialStateEon)

                send_admin_email(
                    subject='DISPUTE! Transfer Delivery.',
                    content='{} {} {}'.format(challenge.wallet.address, challenge.recipient.address, transfer_index))

                # TODO signal critical failure if this does not succeed!
                transaction = contract_interface.queue_answer_delivery_challenge(
                    challenge=challenge,
                    tx_trail=transfer_index,
                    allotment_chain=[crypto.zfill(crypto.decode_hex(v)) for v in
                                     long_string_to_list(recipient_balance.merkle_proof_hashes, 64)],
                    membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                      long_string_to_list(token_commitment.membership_hashes, 64)],
                    values=csf_to_list(
                        recipient_balance.merkle_proof_values, int),
                    l_r=[int(recipient_balance.left),
                         int(recipient_balance.right)],
                    deltas=[d for d in recipient_balance.deltas()],
                    tx_set_root=crypto.decode_hex(
                        recipient_balance.transaction_set_root()),
                    tx_chain=[crypto.zfill(x) for x in transfer_proof],
                    passive_checksum=passive_checksum,
                    passive_amount=passive_amount,
                    passive_marker=passive_marker)

            # swap challenge
            elif challenge.wallet.token != challenge.recipient.token and challenge.wallet.address == challenge.recipient.address:
                try:
                    transfer = Transfer.objects.get(
                        recipient=challenge.recipient,
                        eon_number=challenge_entry.initialStateEon,
                        nonce=challenge_entry.deliveredTxNonce)
                except Transfer.DoesNotExist:
                    logger.error(
                        "Could not find transfer for {} at eon {} with nonce {}."
                        .format(challenge.recipient.address, challenge.eon_number, challenge_entry.deliveredTxNonce))
                    send_admin_email(
                        subject='DISPUTE! NO SWAP!',
                        content="Could not find transfer for {} at eon {} with nonce {}."
                        .format(challenge.recipient.address, challenge.eon_number, challenge_entry.deliveredTxNonce))
                    return

                recipient_transfer_context = WalletTransferContext(
                    wallet=challenge.recipient, transfer=None)

                # if not initial transfer in a multi eon swap
                # override starting balance to cached starting balance
                if Transfer.objects.filter(eon_number=transfer.eon_number-1, tx_id=transfer.tx_id).exists():
                    starting_balance = int(transfer.recipient_starting_balance)
                else:
                    starting_balance = int(recipient_transfer_context.starting_balance_in_eon(
                        challenge_entry.initialStateEon))

                transfers_list_nonce_index_map = {}
                transfers_list = recipient_transfer_context.authorized_transfers_list_shorthand(
                    only_appended=True,
                    force_append=False,
                    eon_number=challenge_entry.initialStateEon,
                    last_transfer_is_finalized=True,
                    index_map=transfers_list_nonce_index_map,
                    starting_balance=starting_balance)

                transfer_tree = TransactionMerkleTree(transfers_list)
                transfer_index = transfers_list_nonce_index_map.get(
                    transfer.nonce)
                transfer_node = transfer_tree.merkle_tree_leaf_map.get(
                    transfer_index)
                transfer_proof = [node.get('hash') for node in calculate_merkle_proof(
                    transfer_index, transfer_node)]

                passive_checksum, passive_amount, passive_marker = recipient_transfer_context.get_passive_values(
                    eon_number=challenge_entry.initialStateEon)

                send_admin_email(
                    subject='DISPUTE! Swap Delivery.',
                    content='{} {} {}'.format(challenge.wallet.address, challenge.recipient.address, transfer_index))

                is_cancelled = transfer.cancelled and transfer.recipient_cancellation_active_state is not None
                if transfer.complete or is_cancelled:
                    starting_balance = 2 ** 256 - 1

                # TODO signal critical failure if this does not succeed!
                transaction = contract_interface.queue_answer_swap_challenge(
                    challenge=challenge,
                    token_pair=[
                        challenge.wallet.token.address,
                        challenge.recipient.token.address],
                    balance_at_start_of_eon=starting_balance,
                    tx_trail=int(transfer_index),
                    allotment_chain=[crypto.zfill(crypto.decode_hex(v)) for v in
                                     long_string_to_list(recipient_balance.merkle_proof_hashes, 64)],
                    membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                      long_string_to_list(token_commitment.membership_hashes, 64)],
                    values=csf_to_list(
                        recipient_balance.merkle_proof_values, int),
                    l_r=[
                        int(recipient_balance.left),
                        int(recipient_balance.right)],
                    deltas=[d for d in recipient_balance.deltas()],
                    tx_set_root=crypto.zfill(crypto.decode_hex(
                        recipient_balance.transaction_set_root())),
                    tx_chain=[crypto.zfill(x) for x in transfer_proof],
                    passive_checksum=passive_checksum,
                    passive_amount=passive_amount,
                    passive_marker=passive_marker)

            challenge.rebuted = True
            challenge.save()
            logger.warning(transaction)
