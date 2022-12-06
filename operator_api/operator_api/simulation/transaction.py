from django.urls import reverse
from eth_utils import remove_0x_prefix
from rest_framework import status
from contractor.rpctestcase import RPCTestCase
from operator_api.simulation.deposit import create_deposits
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Wallet, Transfer, ActiveState, Signature, MinimumAvailableBalanceMarker, Token
from operator_api.crypto import encode_signature, sign_message, hex_value
import random
import datetime
import json
from transactor.tasks.process_passive_transfers import process_passive_transfers_for_eon


def send_transaction(test_case, eon_number, sender, recipient, amount, nonce, token, expected_status=status.HTTP_201_CREATED):
    # Sender account
    sender_wallet = Wallet.objects.get(
        address=remove_0x_prefix(sender.get('address')), token=token)
    # Recipient account
    recipient_wallet = Wallet.objects.get(
        address=remove_0x_prefix(recipient.get('address')), token=token)

    transfer = Transfer(
        wallet=sender_wallet,
        amount=amount,
        eon_number=eon_number,
        recipient=recipient_wallet,
        nonce=nonce,
        passive=True)

    sender_view_context = WalletTransferContext(
        wallet=sender_wallet, transfer=transfer)
    sender_highest_spent, sender_highest_gained = sender_view_context.off_chain_actively_sent_received_amounts(
        eon_number=eon_number,
        only_appended=False)
    updated_spendings = sender_highest_spent + amount

    # Authorize transaction
    transfer_set_root = hex_value(sender_view_context.authorized_transfers_tree_root(
        only_appended=False,
        force_append=True))
    active_state = ActiveState(
        wallet=sender_wallet,
        updated_spendings=updated_spendings,
        updated_gains=sender_highest_gained,
        eon_number=eon_number,
        tx_set_hash=transfer_set_root)
    sender_active_state_authorization = sign_message(
        active_state.checksum(), sender.get('pk'))

    sender_active_state_signature = Signature(
        wallet=sender_wallet,
        checksum=hex_value(active_state.checksum()),
        value=encode_signature(sender_active_state_authorization))

    test_case.assertTrue(sender_active_state_signature.is_valid())

    _, available_balance = sender_view_context.can_send_transfer(
        current_eon_number=eon_number,
        using_only_appended_funds=False)

    new_balance = available_balance - transfer.amount

    concise_balance_marker = MinimumAvailableBalanceMarker(
        wallet=sender_wallet,
        eon_number=eon_number,
        amount=new_balance)
    sender_concise_balance_marker_authorization = sign_message(
        concise_balance_marker.checksum(), sender.get('pk'))

    concise_balance_marker_signature = Signature(
        wallet=sender_wallet,
        checksum=hex_value(concise_balance_marker.checksum()),
        value=encode_signature(sender_concise_balance_marker_authorization))

    test_case.assertTrue(concise_balance_marker_signature.is_valid())

    print("Sender view:")
    print("available_balance:", available_balance)
    print("transfer_set_root:", transfer_set_root)
    print("active_state.updated_spendings:", active_state.updated_spendings)
    print("active_state.updated_gains:", active_state.updated_gains)

    # Make API Request
    url = reverse('transfer-endpoint')
    data = {
        'debit_signature': {
            'value': encode_signature(sender_active_state_authorization),
        },
        'debit_balance_signature': {
            'value': encode_signature(sender_concise_balance_marker_authorization),
        },
        'debit_balance': new_balance,
        'eon_number': eon_number,
        'amount': amount,
        'nonce': nonce,
        'wallet': {
            'address': sender_wallet.address,
            'token': sender_wallet.token.address,
        },
        'recipient': {
            'address': recipient_wallet.address,
            'token': recipient_wallet.token.address,
        },
    }

    # Send tx to server
    x = datetime.datetime.now()
    response = test_case.client.post(url, data, format='json')
    y = datetime.datetime.now()
    delta = y-x

    # Ensure the transaction was recorded
    test_case.assertEqual(response.status_code, expected_status, '\n'.join(
        [url, str(data), str(response.content)]))

    print('TX Time: {}s for {}'.format(delta, amount))

    # fo rpassive transfer assert that transaction is confirmed
    tx = json.loads(response.content)
    transfer = Transfer.objects.get(id=tx['id'])
    test_case.assertTrue(transfer.complete)
    test_case.assertTrue(transfer.appended)
    test_case.assertNotEqual(
        transfer.sender_active_state.operator_signature, None)

    # Log time delta
    return delta


def make_random_valid_transactions(test_case: RPCTestCase, eon_number, accounts, token: Token, make_deposits=True):
    print('Making random valid transactions.')
    transfer_starting_count = Transfer.objects.count()
    active_state_starting_count = ActiveState.objects.count()
    balance_marker_starting_count = MinimumAvailableBalanceMarker.objects.count()
    signature_starting_count = Signature.objects.count()

    if make_deposits:
        create_deposits(test_case, accounts, token)

    transactions = 50

    tx_amount = 0
    time_to_send = datetime.timedelta(0)

    ids = [Wallet.objects.get(address=remove_0x_prefix(
        account.get('address')), token=token).pk for account in accounts]

    passive_transfers = 0

    for i in range(transactions):
        # Randomly choose two wallets
        a, b = 0, 0
        while a == b:
            a = random.randint(2, len(ids))
            b = random.randint(2, len(ids))

        # Sender account
        sender = Wallet.objects.get(pk=ids[a-1])
        available = WalletTransferContext(wallet=sender, transfer=None)\
            .available_funds_at_eon(eon_number=eon_number, only_appended=False)
        amount = min(available, int(random.random() * available))
        tx_amount += amount
        # Recipient account
        nonce = random.randint(1, 999999)

        # Send tx to server and log time delta
        time_to_send += send_transaction(
            test_case=test_case,
            eon_number=eon_number,
            sender=accounts[a-1],
            recipient=accounts[b-1],
            amount=amount,
            nonce=nonce,
            token=token)

        # Assert expected database state
        executed_transfer_count = i + 1
        test_case.assertEqual(Transfer.objects.count(),
                              transfer_starting_count
                              + executed_transfer_count)
        test_case.assertEqual(MinimumAvailableBalanceMarker.objects.count(),
                              balance_marker_starting_count
                              + executed_transfer_count)

        added_active_states_in_previous_iterations = passive_transfers
        added_active_states_in_current_iteration = 1
        test_case.assertEqual(ActiveState.objects.count(),
                              active_state_starting_count
                              + added_active_states_in_previous_iterations
                              + added_active_states_in_current_iteration)

        added_operator_signatures = passive_transfers
        synchronously_confirmed_passive = 1
        test_case.assertEqual(Signature.objects.count(),
                              signature_starting_count
                              # sender / recipient active state sigs
                              + added_active_states_in_previous_iterations
                              + added_active_states_in_current_iteration
                              + executed_transfer_count  # balance marker sigs
                              + added_operator_signatures
                              + synchronously_confirmed_passive)  # operator sigs on active states

        test_case.assertEqual(Signature.objects.count(),
                              signature_starting_count
                              # sender / recipient active state sigs
                              + added_active_states_in_previous_iterations
                              + added_active_states_in_current_iteration
                              + executed_transfer_count  # balance marker sigs
                              + added_operator_signatures  # operator sigs on active states
                              + added_active_states_in_current_iteration)

        passive_transfers += 1

    average_time_to_send = time_to_send / transactions

    print("Total wei transferred: ", tx_amount)
    print("Average time to send: ", average_time_to_send)
