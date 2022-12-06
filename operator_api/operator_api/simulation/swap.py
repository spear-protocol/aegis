from datetime import datetime
import random
import json

from django.urls import reverse
from eth_utils import remove_0x_prefix
from rest_framework import status
from django.conf import settings

from contractor.rpctestcase import RPCTestCase
from operator_api import crypto
from operator_api.crypto import hex_value, sign_message, encode_signature
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Wallet, Transfer, ActiveState, Signature, MinimumAvailableBalanceMarker, TokenCommitment, RootCommitment
from .transaction import send_transaction
from transactor.tasks import process_passive_transfers
from operator_api.zero_merkle_root_cache import NODE_CACHE
from operator_api import testrpc_accounts, merkle_tree
from operator_api.util import long_string_to_list, csf_to_list
from operator_api.tx_merkle_tree import TransactionMerkleTree
from operator_api.merkle_tree import calculate_merkle_proof


def send_swap(test_case: RPCTestCase, eon_number, account, token, token_swapped, amount, amount_swapped, nonce, expected_status=status.HTTP_201_CREATED, eon_count=1, sell_order=True):
    # Sender account
    sender_wallet = Wallet.objects.get(
        address=remove_0x_prefix(account.get('address')), token=token)
    # Recipient account
    recipient_wallet = Wallet.objects.get(address=remove_0x_prefix(
        account.get('address')), token=token_swapped)

    sender_wallet_context = WalletTransferContext(
        wallet=sender_wallet, transfer=None)
    recipient_wallet_context = WalletTransferContext(
        wallet=recipient_wallet, transfer=None)

    initial_sender_balance = sender_wallet_context.available_funds_at_eon(
        eon_number=eon_number, only_appended=False)
    initial_recipient_balance = recipient_wallet_context.available_funds_at_eon(
        eon_number=eon_number, only_appended=False)

    if initial_sender_balance < amount:
        send_transaction(
            test_case=test_case,
            eon_number=eon_number,
            sender=testrpc_accounts.accounts[0],
            recipient=account,
            amount=amount-initial_sender_balance,
            nonce=random.randint(1, 999999),
            token=token)
    if initial_sender_balance > amount:
        # clear sender account
        send_transaction(
            test_case=test_case,
            eon_number=eon_number,
            sender=account,
            recipient=testrpc_accounts.accounts[0],
            amount=initial_sender_balance-amount,
            nonce=random.randint(1, 999999),
            token=token)
    if initial_recipient_balance > 0:
        # clear recipient account
        send_transaction(
            test_case=test_case,
            eon_number=eon_number,
            sender=account,
            recipient=testrpc_accounts.accounts[0],
            amount=initial_recipient_balance,
            nonce=random.randint(1, 999999),
            token=token_swapped)

    sender_balance = sender_wallet_context.available_funds_at_eon(
        eon_number=eon_number, only_appended=False)
    recipient_balance = recipient_wallet_context.available_funds_at_eon(
        eon_number=eon_number, only_appended=False)

    test_case.assertEqual(sender_balance, amount)
    test_case.assertEqual(recipient_balance, 0)

    debit_balance_signatures = []
    debit_signatures = []
    credit_balance_signatures = []
    credit_signatures = []
    fulfillment_signatures = []

    for i in range(eon_count):
        swap = Transfer(
            wallet=sender_wallet,
            amount=amount,
            eon_number=eon_number + i,
            recipient=recipient_wallet,
            amount_swapped=amount_swapped,
            nonce=nonce,
            processed=False,
            complete=False,
            swap=True)

        sender_wallet_context = WalletTransferContext(
            wallet=sender_wallet, transfer=swap)
        recipient_wallet_context = WalletTransferContext(
            wallet=recipient_wallet, transfer=swap)

        sender_highest_spent, sender_highest_gained = sender_wallet_context.off_chain_actively_sent_received_amounts(
            eon_number=eon_number + i,
            only_appended=False)

        if i == 0:
            tx_set_tree = sender_wallet_context.authorized_transfers_tree(
                only_appended=False,
                force_append=True)
        else:
            tx_set_tree = WalletTransferContext.authorized_transfers_tree_from_list([
                swap.shorthand(
                    sender_wallet_context, is_last_transfer=True, starting_balance=sender_balance)
            ])

        tx_set_hash = hex_value(tx_set_tree.root_hash())

        debiting_active_state = ActiveState(
            wallet=sender_wallet,
            updated_spendings=sender_highest_spent + amount,
            updated_gains=sender_highest_gained,
            eon_number=eon_number + i,
            tx_set_hash=tx_set_hash)
        debiting_active_state_authorization = sign_message(
            debiting_active_state.checksum(), account.get('pk'))

        debiting_active_state_signature = Signature(
            wallet=sender_wallet,
            checksum=hex_value(debiting_active_state.checksum()),
            value=encode_signature(debiting_active_state_authorization))

        test_case.assertTrue(debiting_active_state_signature.is_valid())

        debit_concise_balance_marker = MinimumAvailableBalanceMarker(
            wallet=sender_wallet,
            eon_number=eon_number + i,
            amount=0)
        debit_concise_balance_marker_authorization = sign_message(
            debit_concise_balance_marker.checksum(), account.get('pk'))

        debit_concise_balance_marker_signature = Signature(
            wallet=sender_wallet,
            checksum=hex_value(debit_concise_balance_marker.checksum()),
            value=encode_signature(debit_concise_balance_marker_authorization))

        test_case.assertTrue(debit_concise_balance_marker_signature.is_valid())

        recipient_highest_spent, recipient_highest_gained = recipient_wallet_context.off_chain_actively_sent_received_amounts(
            eon_number=eon_number + i,
            only_appended=False)

        if i == 0:
            tx_set_tree = recipient_wallet_context.authorized_transfers_tree(
                only_appended=False,
                force_append=True)
        else:
            tx_set_tree = WalletTransferContext.authorized_transfers_tree_from_list([
                swap.shorthand(
                    recipient_wallet_context, is_last_transfer=True, starting_balance=recipient_balance)
            ])

        tx_set_hash = hex_value(tx_set_tree.root_hash())

        crediting_active_state = ActiveState(
            wallet=recipient_wallet,
            updated_spendings=recipient_highest_spent,
            updated_gains=recipient_highest_gained,
            eon_number=eon_number + i,
            tx_set_hash=tx_set_hash)
        crediting_active_state_authorization = sign_message(
            crediting_active_state.checksum(), account.get('pk'))

        crediting_active_state_signature = Signature(
            wallet=recipient_wallet,
            checksum=hex_value(crediting_active_state.checksum()),
            value=encode_signature(crediting_active_state_authorization))

        test_case.assertTrue(crediting_active_state_signature.is_valid())

        credit_concise_balance_marker = MinimumAvailableBalanceMarker(
            wallet=recipient_wallet,
            eon_number=eon_number + i,
            amount=0)
        credit_concise_balance_marker_authorization = sign_message(
            credit_concise_balance_marker.checksum(), account.get('pk'))

        credit_concise_balance_marker_signature = Signature(
            wallet=recipient_wallet,
            checksum=hex_value(credit_concise_balance_marker.checksum()),
            value=encode_signature(credit_concise_balance_marker_authorization))

        test_case.assertTrue(
            credit_concise_balance_marker_signature.is_valid())

        swap.processed, swap.complete = True, True

        if i == 0:
            tx_set_tree = recipient_wallet_context.authorized_transfers_tree(
                only_appended=False,
                force_append=True)
        else:
            tx_set_tree = WalletTransferContext.authorized_transfers_tree_from_list([
                swap.shorthand(recipient_wallet_context,
                               is_last_transfer=True, starting_balance=0)
            ])

        tx_set_hash = hex_value(tx_set_tree.root_hash())

        recipient_fulfillment_active_state = ActiveState(
            wallet=recipient_wallet,
            updated_spendings=recipient_highest_spent,
            updated_gains=recipient_highest_gained + amount_swapped,
            eon_number=eon_number + i,
            tx_set_hash=tx_set_hash)
        recipient_fulfillment_active_state_authorization = sign_message(
            recipient_fulfillment_active_state.checksum(), account.get('pk'))
        swap.processed, swap.complete = False, False

        recipient_fulfillment_active_state_signature = Signature(
            wallet=recipient_wallet,
            checksum=hex_value(recipient_fulfillment_active_state.checksum()),
            value=encode_signature(recipient_fulfillment_active_state_authorization))

        test_case.assertTrue(
            recipient_fulfillment_active_state_signature.is_valid())

        debit_balance_signatures.append({
            'value': encode_signature(debit_concise_balance_marker_authorization)
        })
        debit_signatures.append({
            'value': encode_signature(debiting_active_state_authorization)
        })
        credit_balance_signatures.append({
            'value': encode_signature(credit_concise_balance_marker_authorization)
        })
        credit_signatures.append({
            'value': encode_signature(crediting_active_state_authorization)
        })
        fulfillment_signatures.append({
            'value': encode_signature(recipient_fulfillment_active_state_authorization)
        })

    # Make API Request
    url = reverse('swap-endpoint')
    data = {
        'debit_signature': debit_signatures,
        'debit_balance_signature': debit_balance_signatures,
        'credit_signature': credit_signatures,
        'credit_balance_signature': credit_balance_signatures,
        'credit_fulfillment_signature': fulfillment_signatures,
        'eon_number': eon_number,
        'amount': amount,
        'amount_swapped': amount_swapped,
        'nonce': nonce,
        'wallet': {
            'address': sender_wallet.address,
            'token': sender_wallet.token.address,
        },
        'recipient': {
            'address': recipient_wallet.address,
            'token': recipient_wallet.token.address,
        },
        'sell_order': sell_order
    }

    # Send tx to server
    x = datetime.now()
    response = test_case.client.post(url, data, format='json')
    y = datetime.now()
    delta = y-x

    # Ensure the transaction was recorded
    test_case.assertEqual(response.status_code,
                          expected_status, response.content)

    print('SWAP Time: {}s for {}/{}'.format(delta, amount, amount_swapped))

    # assert that swap created for current eon is confirmed
    tx = json.loads(response.content)
    swap = Transfer.objects.get(id=tx['id'])
    test_case.assertEqual(swap.eon_number, eon_number)
    test_case.assertTrue(swap.is_signed_by_operator())

    # Log time delta
    return delta


def get_last_swap(token, token_swapped, account):
    # Sender account
    sender_wallet = Wallet.objects.get(
        address=remove_0x_prefix(account.get('address')), token=token)
    # Recipient account
    recipient_wallet = Wallet.objects.get(address=remove_0x_prefix(
        account.get('address')), token=token_swapped)

    return Transfer.objects.filter(
        wallet=sender_wallet,
        recipient=recipient_wallet,
        swap=True)\
        .order_by('time')\
        .last()


def freeze_last_swap(test_case: RPCTestCase, token, token_swapped, account, expected_status=status.HTTP_200_OK):
    swap = get_last_swap(token, token_swapped, account)
    return freeze_swap(test_case=test_case, swap=swap, account=account, expected_status=expected_status)


def freeze_swap(test_case: RPCTestCase, swap: Transfer, account, expected_status=status.HTTP_200_OK):
    freeze_authorization = sign_message(
        swap.swap_cancellation_message_checksum(), account.get('pk'))
    # Make API Request
    url = reverse('freeze-swap-endpoint', kwargs={'pk': swap.id})
    data = {
        'freezing_signature': {
            'value': encode_signature(freeze_authorization)
        }
    }

    # Send tx to server
    x = datetime.now()
    response = test_case.client.put(url, data, format='json')
    y = datetime.now()
    delta = y-x

    # Ensure the transaction was recorded
    test_case.assertEqual(response.status_code,
                          expected_status, response.content)

    print('FREEZE Time: {}s'.format(delta))

    # Log time delta
    return delta


def finalize_last_swap(test_case: RPCTestCase, token, token_swapped, account, expected_status=status.HTTP_200_OK, eon_count=1):
    swap = get_last_swap(token, token_swapped, account)
    return finalize_swap(test_case=test_case, swap=swap, account=account, expected_status=expected_status, eon_count=eon_count)


def finalize_swap(test_case: RPCTestCase, swap: Transfer, account, expected_status=status.HTTP_200_OK, eon_count=1):
    print('FINALIZING {} ({}/{})'.format(swap.id,
                                         int(swap.amount), int(swap.amount_swapped)))

    finalization_authorizations = []
    test_case.assertTrue(swap.complete)

    recipient_view_context = WalletTransferContext(
        wallet=swap.recipient, transfer=swap)

    tx_set_tree = recipient_view_context.authorized_transfers_tree(
        only_appended=False,
        force_append=True)
    tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
    transfer_index = tx_set_tree.merkle_tree_nonce_map.get(swap.nonce)
    transfer_proof = tx_set_tree.proof(transfer_index)

    highest_spendings, highest_gains = recipient_view_context.off_chain_actively_sent_received_amounts(
        eon_number=swap.eon_number,
        only_appended=False)

    print("Finalize spent {} gained {}".format(
        highest_spendings, highest_gains))

    for state in ActiveState.objects.filter(wallet=swap.recipient, eon_number=swap.eon_number):
        print(state.id)
        print("Finalize spent {} gained {}".format(
            state.updated_spendings, state.updated_gains))

    finalization_active_state = ActiveState(
        wallet=swap.recipient,
        updated_spendings=highest_spendings + swap.amount_swapped,
        updated_gains=highest_gains + swap.amount_swapped,
        tx_set_hash=tx_set_hash,
        tx_set_proof_hashes=transfer_proof,
        tx_set_index=transfer_index,
        eon_number=swap.eon_number)

    finalization_authorizations.append({
        'value': encode_signature(sign_message(finalization_active_state.checksum(), account.get('pk')))
    })

    for i in range(1, eon_count):
        future_spent_gained = max(
            highest_spendings, highest_gains) + swap.amount_swapped + 1
        empty_tx_set_hash = crypto.hex_value(NODE_CACHE[0]['hash'])
        finalization_active_state = ActiveState(
            wallet=swap.recipient,
            updated_spendings=future_spent_gained,
            updated_gains=future_spent_gained,
            tx_set_hash=empty_tx_set_hash,
            # any dummy value
            tx_set_proof_hashes='',
            # any dummy value
            tx_set_index=0,
            eon_number=swap.eon_number + i)

        finalization_authorizations.append({
            'value': encode_signature(sign_message(finalization_active_state.checksum(), account.get('pk')))
        })

    # Make API Request
    url = reverse('finalize-swap-endpoint', kwargs={'pk': swap.id})
    data = {
        'finalization_signature': finalization_authorizations
    }

    # Send tx to server
    x = datetime.now()
    response = test_case.client.put(url, data, format='json')
    y = datetime.now()
    delta = y-x

    # Ensure the transaction was recorded
    test_case.assertEqual(response.status_code,
                          expected_status, response.content)

    print('FINALIZE Time: {}s'.format(delta))

    # Log time delta
    return delta


def cancel_last_swap(test_case: RPCTestCase, token, token_swapped, account, expected_status=status.HTTP_200_OK, eon_count=1):
    swap = get_last_swap(token, token_swapped, account)
    return cancel_swap(test_case=test_case, swap=swap, account=account, expected_status=expected_status, eon_count=eon_count)


def cancel_swap(test_case: RPCTestCase, swap: Transfer, account, expected_status=status.HTTP_200_OK, eon_count=1):
    sender_cancellation_authorizations = []
    recipient_cancellation_authorizations = []

    sender_view_context = WalletTransferContext(
        wallet=swap.wallet,
        transfer=swap)

    tx_set_tree = sender_view_context.authorized_transfers_tree(
        only_appended=False,
        force_append=False,
        assume_active_state_exists=True)
    tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
    transfer_index = tx_set_tree.merkle_tree_nonce_map.get(swap.nonce)
    transfer_proof = tx_set_tree.proof(transfer_index)

    sender_highest_spendings, sender_highest_gains = sender_view_context.off_chain_actively_sent_received_amounts(
        eon_number=swap.eon_number,
        only_appended=False)

    matched_out, _ = swap.matched_amounts()

    sender_highest_gains += swap.amount - matched_out

    sender_cancellation_active_state = ActiveState(
        wallet=swap.wallet,
        updated_spendings=sender_highest_spendings,
        updated_gains=sender_highest_gains,
        tx_set_hash=tx_set_hash,
        tx_set_proof_hashes=transfer_proof,
        tx_set_index=transfer_index,
        eon_number=swap.eon_number)

    recipient_view_context = WalletTransferContext(
        wallet=swap.recipient,
        transfer=swap)

    tx_set_tree = recipient_view_context.authorized_transfers_tree(
        only_appended=False,
        force_append=False,
        assume_active_state_exists=True)
    tx_set_hash = crypto.hex_value(tx_set_tree.root_hash())
    transfer_index = tx_set_tree.merkle_tree_nonce_map.get(swap.nonce)
    transfer_proof = tx_set_tree.proof(transfer_index)

    recipient_highest_spendings, recipient_highest_gains = recipient_view_context.off_chain_actively_sent_received_amounts(
        eon_number=swap.eon_number,
        only_appended=False)

    recipient_cancellation_active_state = ActiveState(
        wallet=swap.recipient,
        updated_spendings=recipient_highest_spendings + swap.amount_swapped,
        updated_gains=recipient_highest_gains + swap.amount_swapped,
        tx_set_hash=tx_set_hash,
        tx_set_proof_hashes=transfer_proof,
        tx_set_index=transfer_index,
        eon_number=swap.eon_number)

    sender_cancellation_authorizations.append({
        'value': encode_signature(sign_message(sender_cancellation_active_state.checksum(), account.get('pk')))
    })
    recipient_cancellation_authorizations.append({
        'value': encode_signature(sign_message(recipient_cancellation_active_state.checksum(), account.get('pk')))
    })

    for i in range(1, eon_count):
        empty_tx_set_hash = crypto.hex_value(NODE_CACHE[0]['hash'])
        sender_future_spent_gained = max(
            sender_highest_spendings, sender_highest_gains) + 1
        recipient_future_spent_gained = max(
            recipient_highest_spendings, recipient_highest_gains) + swap.amount_swapped + 1

        sender_cancellation_active_state = ActiveState(
            wallet=swap.wallet,
            updated_spendings=sender_future_spent_gained,
            updated_gains=sender_future_spent_gained,
            tx_set_hash=empty_tx_set_hash,
            # any dummy value
            tx_set_proof_hashes='',
            # any dummy value
            tx_set_index=0,
            eon_number=swap.eon_number + i)

        recipient_cancellation_active_state = ActiveState(
            wallet=swap.recipient,
            updated_spendings=recipient_future_spent_gained,
            updated_gains=recipient_future_spent_gained,
            tx_set_hash=empty_tx_set_hash,
            # any dummy value
            tx_set_proof_hashes='',
            # any dummy value
            tx_set_index=0,
            eon_number=swap.eon_number + i)

        sender_cancellation_authorizations.append({
            'value': encode_signature(sign_message(sender_cancellation_active_state.checksum(), account.get('pk')))
        })
        recipient_cancellation_authorizations.append({
            'value': encode_signature(sign_message(recipient_cancellation_active_state.checksum(), account.get('pk')))
        })

    # Make API Request
    url = reverse('cancel-swap-endpoint', kwargs={'pk': swap.id})
    data = {
        'sender_cancellation_signature': sender_cancellation_authorizations,
        'recipient_cancellation_signature': recipient_cancellation_authorizations
    }

    # Send tx to server
    x = datetime.now()
    response = test_case.client.put(url, data, format='json')
    y = datetime.now()
    delta = y-x

    # Ensure the transaction was recorded
    test_case.assertEqual(response.status_code,
                          expected_status, response.content)

    print('CANCEL Time: {}s'.format(delta))

    # Log time delta
    return delta


def init_swap_challenge(test_case: RPCTestCase, swap: Transfer, eon_number):
    sender_transfer_context = WalletTransferContext(
        wallet=swap.wallet, transfer=None)

    if Transfer.objects.filter(eon_number=swap.eon_number-1, tx_id=swap.tx_id).exists():
        starting_balance = int(swap.sender_starting_balance)
    else:
        starting_balance = int(
            sender_transfer_context.starting_balance_in_eon(eon_number))

    transfers_list_nonce_index_map = {}
    transfers_list = sender_transfer_context.authorized_transfers_list_shorthand(
        only_appended=True,
        force_append=False,
        eon_number=eon_number,
        last_transfer_is_finalized=True,
        index_map=transfers_list_nonce_index_map,
        starting_balance=starting_balance)

    sender_active_state = sender_transfer_context.last_appended_active_state(
        eon_number=eon_number)

    transfer_tree = TransactionMerkleTree(transfers_list)
    transfer_index = transfers_list_nonce_index_map.get(
        int(swap.nonce))
    transfer_node = transfer_tree.merkle_tree_leaf_map.get(transfer_index)
    transfer_proof = [node.get('hash') for node in calculate_merkle_proof(
        transfer_index, transfer_node)]

    test_case.assertEqual(sender_active_state.tx_set_hash,
                          crypto.hex_value(transfer_tree.root_hash()))

    tx_set_root = crypto.zfill(
        crypto.decode_hex(sender_active_state.tx_set_hash))
    deltas = [int(sender_active_state.updated_spendings),
              int(sender_active_state.updated_gains)]

    test_case.assertTrue(test_case.contract_interface.check_merkle_membership_proof(
        trail=int(transfer_index),
        chain=[crypto.zfill(x) for x in transfer_proof],
        node=transfer_node.get('hash'),
        merkle_root=tx_set_root))

    token_commitment = TokenCommitment.objects.get(
        token=swap.wallet.token,
        root_commitment__eon_number=eon_number+1)

    v, r, s = sender_active_state.operator_signature.vrs()

    # swap_sender_balance = sender_transfer_context.balance_as_of_eon(
    #     eon_number)
    sender_balance = sender_transfer_context.balance_as_of_eon(
        eon_number+1)

    passive_checksum, passive_amount, passive_marker = sender_transfer_context.get_passive_values(
        eon_number=eon_number+1)

    swap_order = [
        int(swap.amount),  # sell
        int(swap.amount_swapped),  # buy
        # int(swap_sender_balance.right - swap_sender_balance.left),
        starting_balance,  # balance
        int(swap.nonce)]  # nonce

    chain_transition_checksum = test_case.contract_interface.check_proof_of_transition_agreement(
        token_address=swap.wallet.token.address,
        holder=swap.wallet.address,
        trail_identifier=swap.wallet.trail_identifier,
        eon_number=eon_number,
        tx_set_root=tx_set_root,
        deltas=deltas,
        attester=settings.HUB_OWNER_ACCOUNT_ADDRESS,
        r=crypto.uint256(r), s=crypto.uint256(s), v=v)
    test_case.assertEqual(
        crypto.hex_value(sender_active_state.checksum()),
        crypto.hex_value(chain_transition_checksum))

    node_hash = merkle_tree.leaf_hash(
        merkle_tree.wallet_leaf_inner_hash,
        {
            'contract': settings.HUB_LQD_CONTRACT_ADDRESS,
            'token': swap.wallet.token.address,
            'wallet': swap.wallet.address,
            'left': sender_balance.left,
            'right': sender_balance.right,
            'active_state_checksum': sender_active_state.checksum(),
            'passive_checksum': passive_checksum,
            'passive_amount': passive_amount,
            'passive_marker': passive_marker,
        })
    checkpoint = RootCommitment.objects.get(eon_number=eon_number+1)
    test_case.contract_interface.check_exclusive_allotment_proof(
        allotment_trail=int(sender_balance.merkle_proof_trail),
        membership_trail=swap.wallet.token.trail,
        node=node_hash,
        merkle_root=crypto.decode_hex(checkpoint.merkle_root),
        allotment_chain=[crypto.zfill(crypto.decode_hex(v)) for v in
                         long_string_to_list(sender_balance.merkle_proof_hashes, 64)],
        membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                          long_string_to_list(token_commitment.membership_hashes, 64)],
        value=csf_to_list(sender_balance.merkle_proof_values, int),
        left=int(sender_balance.left),
        right=int(sender_balance.right)
    )

    test_case.contract_interface.issue_swap_challenge(
        token_pair=[
            swap.wallet.token.address,
            swap.recipient.token.address],
        wallet=swap.wallet.address,
        swap_order=swap_order,
        sender_tx_recipient_trails=[
            swap.wallet.trail_identifier,
            int(transfer_index),
            swap.recipient.trail_identifier],
        allotment_chain=[crypto.zfill(crypto.decode_hex(v)) for v in
                         long_string_to_list(sender_balance.merkle_proof_hashes, 64)],
        membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                          long_string_to_list(token_commitment.membership_hashes, 64)],
        tx_chain=[crypto.zfill(x) for x in transfer_proof],
        values=csf_to_list(sender_balance.merkle_proof_values, int),
        l_r=[
            int(sender_balance.left),
            int(sender_balance.right)],
        tx_set_root=tx_set_root,
        deltas=deltas,
        passive_checksum=passive_checksum,
        passive_amount=passive_amount,
        passive_marker=passive_marker)
