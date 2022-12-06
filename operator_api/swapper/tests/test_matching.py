import random

from operator_api.simulation.swap import send_swap, freeze_last_swap, finalize_last_swap, cancel_last_swap, finalize_swap
from ledger.models import Transfer
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps_for_eon
from swapper.tasks.confirm_swaps import confirm_swaps_for_eon
from swapper.tasks.process_swaps import process_swaps_for_eon
from operator_api.simulation.eon import commit_eon, advance_to_next_eon
from ledger.context.wallet_transfer import WalletTransferContext
from .swap_test_case import SwapTestCase


class MatchingSwapTests(SwapTestCase):
    def test_match_multi_eon_swap(self):
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
            amount=1,
            amount_swapped=2,
            nonce=buy_lqd_nonce,
            eon_count=total_remaining_eons)

        self.assertEqual(Transfer.objects.filter(
            swap=True).count(), total_remaining_eons)

        swap = Transfer.objects.filter(swap=True)[0]
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
        for i in range(3, 6):
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

        # make opposite swap
        send_swap(  # Sell LQD at 0.5 ETH
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

        swap1 = Transfer.objects.filter(eon_number=5).order_by('time')[0]
        swap2 = Transfer.objects.filter(eon_number=5).order_by('time')[1]

        self.assertNotEqual(swap1.tx_id, swap2.tx_id)

        # finalize swaps
        swap = Transfer.objects.get(swap=True, tx_id=swap_tx_id, eon_number=5)
        self.assertEqual(Transfer.objects.filter(
            tx_id=swap_tx_id, eon_number__gt=5, swap=True, voided=False).count(), 0)
        finalize_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1],
            eon_count=total_remaining_eons)
        finalize_last_swap(
            test_case=self,
            token=self.lqd_token,
            token_swapped=self.eth_token,
            account=self.testrpc_accounts[2],
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            5, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            5, False), recipient_funds_before + 2)

    def test_partial_match_multi_eon_swap(self):
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

        total_remaining_eons = 8
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=4,
            amount_swapped=8,
            nonce=buy_lqd_nonce,
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=self.eth_token).order_by('id')[0]
        swap_tx_id = swap.tx_id
        wallet_transfer_context = WalletTransferContext(
            wallet=swap.wallet, transfer=None)
        recipient_transfer_context = WalletTransferContext(
            wallet=swap.recipient, transfer=None)

        wallet_funds_before = 4
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

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            2, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            2, False), recipient_funds_before + 2)
        wallet_funds_before = wallet_funds_before - 1
        recipient_funds_before = recipient_funds_before + 2

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
            swap = Transfer.objects.get(
                swap=True, tx_id=swap_tx_id, eon_number=i)
            self.assertEqual(swap.eon_number, i)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i)
            cancel_finalize_swaps_for_eon(operator_eon_number=i)
            process_swaps_for_eon(operator_eon_number=i)

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i, False), wallet_funds_before)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i, False), recipient_funds_before)

        new_wallet_funds = wallet_funds_before
        new_recipient_funds = recipient_funds_before
        # partial match across eons
        for i in range(5, 8):
            # proceed to next eon
            advance_to_next_eon(
                test_case=self,
                eon_number=i-1)
            commit_eon(
                test_case=self,
                eon_number=i)
            total_remaining_eons -= 1
            swap = Transfer.objects.get(
                swap=True, tx_id=swap_tx_id, eon_number=i)
            self.assertEqual(swap.eon_number, i)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i)
            cancel_finalize_swaps_for_eon(operator_eon_number=i)
            process_swaps_for_eon(operator_eon_number=i)

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i, False), new_wallet_funds)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i, False), new_recipient_funds)

            # make opposite swap
            send_swap(  # Sell LQD at 0.5 ETH
                test_case=self,
                eon_number=i,
                account=self.testrpc_accounts[i-2],
                token=self.lqd_token,
                token_swapped=self.eth_token,
                amount=2,
                amount_swapped=1,
                nonce=sell_lqd_nonce,
                eon_count=1)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i)
            cancel_finalize_swaps_for_eon(operator_eon_number=i)
            process_swaps_for_eon(operator_eon_number=i)

            finalize_last_swap(
                test_case=self,
                token=self.lqd_token,
                token_swapped=self.eth_token,
                account=self.testrpc_accounts[i-2],
                eon_count=1)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i)
            cancel_finalize_swaps_for_eon(operator_eon_number=i)
            process_swaps_for_eon(operator_eon_number=i)

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i, False), new_wallet_funds - 1)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i, False), new_recipient_funds + 2)
            new_wallet_funds = new_wallet_funds - 1
            new_recipient_funds = new_recipient_funds + 2

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=7)
        matched_out, matched_in = swap.matched_amounts(all_eons=True)
        # self.assertTrue(swap.processed)
        self.assertTrue(swap.appended)
        self.assertFalse(swap.voided)
        self.assertFalse(swap.cancelled)
        self.assertEqual(matched_out, 4)
        self.assertEqual(matched_in, 8)
        self.assertTrue(swap.complete)

        self.assertEqual(Transfer.objects.filter(
            tx_id=swap_tx_id, eon_number__gt=7, swap=True, voided=False).count(), 0)
        finalize_swap(
            test_case=self,
            swap=swap,
            account=self.testrpc_accounts[1],
            eon_count=total_remaining_eons
        )

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=7)
        cancel_finalize_swaps_for_eon(operator_eon_number=7)
        process_swaps_for_eon(operator_eon_number=7)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            7, False), wallet_funds_before - 3)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            7, False), recipient_funds_before + 6)

        advance_to_next_eon(
            test_case=self,
            eon_number=7)
        commit_eon(
            test_case=self,
            eon_number=8)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=8)
        cancel_finalize_swaps_for_eon(operator_eon_number=8)
        process_swaps_for_eon(operator_eon_number=8)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            8, False), wallet_funds_before - 3)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            8, False), recipient_funds_before + 6)

    def test_unmatched_swap(self):
        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        # make a valid swap
        send_swap(
            test_case=self,
            eon_number=2,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=random.randint(1, 999999))

        swap = Transfer.objects.filter(swap=True)[0]
        wallet_transfer_context = WalletTransferContext(
            wallet=swap.wallet, transfer=None)

        funds_before = 1

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        # proceed to next eon
        advance_to_next_eon(
            test_case=self,
            eon_number=2)
        commit_eon(
            test_case=self,
            eon_number=3)

        funds_after = wallet_transfer_context.balance_amount_as_of_eon(3)

        self.assertEqual(funds_before, funds_after)

        # make and cancel a swap
        send_swap(
            test_case=self,
            eon_number=3,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=random.randint(1, 999999))

        freeze_last_swap(
            test_case=self,
            token=self.eth_token,
            token_swapped=self.lqd_token,
            account=self.testrpc_accounts[1])
        cancel_last_swap(
            test_case=self,
            token=self.eth_token,
            token_swapped=self.lqd_token,
            account=self.testrpc_accounts[1])

        funds_before = wallet_transfer_context.balance_amount_as_of_eon(3)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=3)
        cancel_finalize_swaps_for_eon(operator_eon_number=3)
        process_swaps_for_eon(operator_eon_number=3)

        # proceed to next eon
        advance_to_next_eon(
            test_case=self,
            eon_number=3)
        commit_eon(
            test_case=self,
            eon_number=4)

        funds_after = wallet_transfer_context.balance_amount_as_of_eon(4)

        self.assertEqual(funds_before, funds_after)
