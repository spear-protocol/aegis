import random

from operator_api.simulation.swap import send_swap, freeze_last_swap, finalize_last_swap, cancel_last_swap, freeze_swap, cancel_swap
from ledger.models import Transfer
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps_for_eon
from swapper.tasks.confirm_swaps import confirm_swaps_for_eon
from swapper.tasks.process_swaps import process_swaps_for_eon
from operator_api.simulation.eon import commit_eon, advance_to_next_eon
from ledger.context.wallet_transfer import WalletTransferContext
from .swap_test_case import SwapTestCase


class SwapCancellationTests(SwapTestCase):
    def test_cancel_multi_eon_swap(self):
        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        buy_lqd_nonce = random.randint(1, 999999)
        sell_lqd_nonce = random.randint(1, 999999)

        total_remaining_eons = 5
        # make persistent swap
        buy_lqd = send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=buy_lqd_nonce,
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=self.eth_token).order_by('id')[0]
        swap_tx_id = swap.tx_id
        wallet_transfer_context = WalletTransferContext(
            wallet=swap.wallet, transfer=None)
        recipient_transfer_context = WalletTransferContext(
            wallet=swap.recipient, transfer=None)

        wallet_funds_before = 1
        recipient_funds_before = 0

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        # skip some eons
        for i in range(3, 5):
            # proceed to next eon
            advance_to_next_eon(
                test_case=self,
                eon_number=i-1)
            commit_eon(
                test_case=self,
                eon_number=i)
            total_remaining_eons -= 1

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i)
            cancel_finalize_swaps_for_eon(operator_eon_number=i)
            process_swaps_for_eon(operator_eon_number=i)

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i, False), wallet_funds_before)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i, False), recipient_funds_before)
            self.assertEqual(wallet_transfer_context.balance_as_of_eon(
                i).amount(), wallet_funds_before)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=4)
        freeze_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1])
        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=4)
        cancel_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1],
            eon_count=total_remaining_eons)
        self.assertEqual(Transfer.objects.filter(
            tx_id=swap_tx_id, eon_number__gt=4, swap=True, voided=False).count(), 0)

        swap = Transfer.objects.filter(swap=True)[0]
        self.assertTrue(swap.cancelled)
        self.assertTrue(swap.processed)
        self.assertTrue(swap.appended)
        self.assertTrue(
            swap.sender_cancellation_active_state.operator_signature is not None)

        # proceed to next eon
        advance_to_next_eon(
            test_case=self,
            eon_number=4)
        commit_eon(
            test_case=self,
            eon_number=5)
        total_remaining_eons -= 1

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        swap = Transfer.objects.filter(swap=True)[0]
        self.assertTrue(swap.cancelled)
        self.assertTrue(swap.processed)
        self.assertTrue(swap.appended)
        self.assertEqual(swap.eon_number, 4)
        self.assertEqual(wallet_transfer_context.balance_as_of_eon(
            5).amount(), wallet_funds_before)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            5, False), wallet_funds_before)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            5, False), recipient_funds_before)

        # make opposite swap
        sell_lqd = send_swap(  # Sell LQD at 0.5 ETH
            test_case=self,
            eon_number=5,
            account=self.testrpc_accounts[2],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=2,
            amount_swapped=1,
            nonce=sell_lqd_nonce,
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            5, False), wallet_funds_before)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            5, False), recipient_funds_before)

        commit_eon(test_case=self, eon_number=5)

    def test_cancel_after_partial_match_multi_eon_swap(self):
        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        buy_lqd_nonce = random.randint(1, 999999)
        sell_lqd_nonce = random.randint(1, 999999)

        total_remaining_eons = 5
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=2,
            amount_swapped=4,
            nonce=buy_lqd_nonce,
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=self.eth_token).order_by('id')[0]
        swap_tx_id = swap.tx_id
        wallet_transfer_context = WalletTransferContext(
            wallet=swap.wallet, transfer=None)
        recipient_transfer_context = WalletTransferContext(
            wallet=swap.recipient, transfer=None)

        wallet_funds_before = 2
        recipient_funds_before = 0

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        # skip some eons
        for i in range(3, 5):
            # proceed to next eon
            advance_to_next_eon(
                test_case=self,
                eon_number=i-1)
            commit_eon(
                test_case=self,
                eon_number=i)
            total_remaining_eons -= 1

            try:
                swap = Transfer.objects.get(
                    swap=True, tx_id=swap_tx_id, eon_number=i)
                self.assertTrue(True)
            except Transfer.DoesNotExist:
                self.assertTrue(False)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i)
            cancel_finalize_swaps_for_eon(operator_eon_number=i)
            process_swaps_for_eon(operator_eon_number=i)

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i, False), wallet_funds_before)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i, False), recipient_funds_before)

        # make opposite swap
        send_swap(  # Sell LQD at 0.5 ETH
            test_case=self,
            eon_number=4,
            account=self.testrpc_accounts[2],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=2,
            amount_swapped=1,
            nonce=sell_lqd_nonce,
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=4)
        cancel_finalize_swaps_for_eon(operator_eon_number=4)
        process_swaps_for_eon(operator_eon_number=4)

        finalize_last_swap(
            test_case=self,
            token=self.lqd_token,
            token_swapped=self.eth_token,
            account=self.testrpc_accounts[2],
            eon_count=1)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            4, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            4, False), recipient_funds_before + 2)

        # proceed to next eon
        advance_to_next_eon(
            test_case=self,
            eon_number=4)
        commit_eon(
            test_case=self,
            eon_number=5)
        total_remaining_eons -= 1

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=5)
        self.assertFalse(swap.processed)
        self.assertTrue(swap.appended)
        self.assertFalse(swap.voided)
        self.assertFalse(swap.cancelled)
        self.assertFalse(swap.complete)
        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            5, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            5, False), recipient_funds_before + 2)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=5)
        freeze_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1])
        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=5)
        cancel_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1],
            eon_count=total_remaining_eons)
        self.assertEqual(Transfer.objects.filter(
            tx_id=swap_tx_id, eon_number__gt=5, swap=True, voided=False).count(), 0)
        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=5)
        self.assertTrue(swap.processed)
        self.assertTrue(swap.appended)
        self.assertFalse(swap.voided)
        self.assertTrue(swap.cancelled)
        self.assertFalse(swap.complete)
        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            5, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            5, False), recipient_funds_before + 2)

        # proceed to next eon
        advance_to_next_eon(
            test_case=self,
            eon_number=5)
        commit_eon(
            test_case=self,
            eon_number=6)
        total_remaining_eons -= 1

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=6)
        cancel_finalize_swaps_for_eon(operator_eon_number=6)
        process_swaps_for_eon(operator_eon_number=6)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=6)
        self.assertTrue(swap.processed)
        self.assertFalse(swap.appended)
        self.assertTrue(swap.voided)
        self.assertTrue(swap.cancelled)
        self.assertFalse(swap.complete)
        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            6, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            6, False), recipient_funds_before + 2)

        # make opposite swap
        send_swap(  # Sell LQD at 0.5 ETH
            test_case=self,
            eon_number=6,
            account=self.testrpc_accounts[3],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=2,
            amount_swapped=1,
            nonce=sell_lqd_nonce,
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=6)
        cancel_finalize_swaps_for_eon(operator_eon_number=6)
        process_swaps_for_eon(operator_eon_number=6)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            6, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            6, False), recipient_funds_before + 2)

        commit_eon(test_case=self, eon_number=6)

    def test_cancel_after_partial_match_swap(self):
        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        buy_lqd_nonce = random.randint(1, 999999)
        sell_lqd_nonce = random.randint(1, 999999)

        total_remaining_eons = 5
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=2,
            amount_swapped=4,
            nonce=buy_lqd_nonce,
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=self.eth_token).order_by('id')[0]
        swap_tx_id = swap.tx_id
        wallet_transfer_context = WalletTransferContext(
            wallet=swap.wallet, transfer=None)
        recipient_transfer_context = WalletTransferContext(
            wallet=swap.recipient, transfer=None)

        wallet_funds_before = 2
        recipient_funds_before = 0

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        # make opposite swap
        send_swap(  # Sell LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=self.testrpc_accounts[2],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=2,
            amount_swapped=1,
            nonce=sell_lqd_nonce,
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        finalize_last_swap(
            test_case=self,
            token=self.lqd_token,
            token_swapped=self.eth_token,
            account=self.testrpc_accounts[2],
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=2)
        freeze_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1])
        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=2)
        cancel_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1],
            eon_count=total_remaining_eons)
        self.assertEqual(Transfer.objects.filter(
            tx_id=swap_tx_id, eon_number__gt=2, swap=True, voided=False).count(), 0)
        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            2, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            2, False), recipient_funds_before + 2)

        advance_to_next_eon(
            test_case=self,
            eon_number=2)
        commit_eon(
            test_case=self,
            eon_number=3)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=3)
        cancel_finalize_swaps_for_eon(operator_eon_number=3)
        process_swaps_for_eon(operator_eon_number=3)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            3, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            3, False), recipient_funds_before + 2)

    def test_swap_freezing(self):
        for i in range(0, 2):
            for account in self.testrpc_accounts[:4]:
                send_swap(  # Buy LQD at 0.5 ETH
                    test_case=self,
                    eon_number=1,
                    account=account,
                    token=self.eth_token,
                    token_swapped=self.lqd_token,
                    amount=1,
                    amount_swapped=2,
                    nonce=random.randint(1, 999999))

            # No Matches, just signatures
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)

            for account in self.testrpc_accounts[:2]:
                freeze_last_swap(
                    test_case=self,
                    account=account,
                    token=self.eth_token,
                    token_swapped=self.lqd_token)
                cancel_last_swap(
                    test_case=self,
                    token=self.eth_token,
                    token_swapped=self.lqd_token,
                    account=account)

            for account in self.testrpc_accounts[4:]:
                send_swap(  # Sell LQD at 0.5 ETH
                    test_case=self,
                    eon_number=1,
                    account=account,
                    token=self.lqd_token,
                    token_swapped=self.eth_token,
                    amount=2,
                    amount_swapped=1,
                    nonce=random.randint(1, 999999))

            # 2 Matches
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)
            for account in self.testrpc_accounts[2:4]:
                finalize_last_swap(
                    test_case=self,
                    token=self.eth_token,
                    token_swapped=self.lqd_token,
                    account=account)
            for account in self.testrpc_accounts[4:6]:
                finalize_last_swap(
                    test_case=self,
                    token=self.lqd_token,
                    token_swapped=self.eth_token,
                    account=account)
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)

            for account in self.testrpc_accounts[6:]:
                freeze_last_swap(
                    test_case=self,
                    account=account,
                    token=self.lqd_token,
                    token_swapped=self.eth_token)
                cancel_last_swap(
                    test_case=self,
                    token=self.lqd_token,
                    token_swapped=self.eth_token,
                    account=account)
