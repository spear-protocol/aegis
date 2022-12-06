import random

from operator_api.simulation.swap import send_swap, freeze_last_swap, finalize_last_swap, cancel_last_swap
from ledger.models import Transfer
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps_for_eon
from swapper.tasks.confirm_swaps import confirm_swaps_for_eon
from swapper.tasks.process_swaps import process_swaps_for_eon
from operator_api.simulation.eon import commit_eon, advance_to_next_eon
from ledger.context.wallet_transfer import WalletTransferContext
from .swap_test_case import SwapTestCase


class GenericSwapTests(SwapTestCase):
    def test_orderbook_sorting(self):
        for idx, account in enumerate(self.testrpc_accounts[:4], 1):
            send_swap(  # Buy LQD at .5, .25, .16, .125, ETH
                test_case=self,
                eon_number=1,
                account=account,
                token=self.eth_token,
                token_swapped=self.lqd_token,
                amount=1,
                amount_swapped=2*idx,
                nonce=random.randint(1, 999999))
            # Match none
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)

        send_swap(  # Sell LQD at 0.5 ETH -> match with BUY at 0.5
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[5],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=2,
            amount_swapped=1,
            nonce=random.randint(1, 999999))
        # Match best
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)
        finalize_last_swap(
            test_case=self,
            token=self.eth_token,
            token_swapped=self.lqd_token,
            account=self.testrpc_accounts[0])
        finalize_last_swap(
            test_case=self,
            token=self.lqd_token,
            token_swapped=self.eth_token,
            account=self.testrpc_accounts[5])
        for account in self.testrpc_accounts[1:4]:
            # Cancel pending .25, .16... BUY orders
            freeze_last_swap(
                test_case=self,
                account=account,
                token=self.eth_token,
                token_swapped=self.lqd_token)
            cancel_last_swap(
                test_case=self,
                account=account,
                token=self.eth_token,
                token_swapped=self.lqd_token)
            # Match none
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)

        # Test OPPOSITE direction
        for idx, account in enumerate(self.testrpc_accounts[:5], 1):
            send_swap(  # SELL LQD at .5, .25, .16, .125, 0.1 ETH
                test_case=self,
                eon_number=1,
                account=account,
                token=self.lqd_token,
                token_swapped=self.eth_token,
                amount=200000*idx,
                amount_swapped=100000,
                nonce=random.randint(1, 999999))
            # Match none
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)

        send_swap(  # BUY LQD at 0.5 ETH -> match with SELL at 0.1
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[5],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=100000,
            amount_swapped=200000,
            nonce=random.randint(1, 999999))
        # Match best
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)
        finalize_last_swap(
            test_case=self,
            token=self.lqd_token,
            token_swapped=self.eth_token,
            account=self.testrpc_accounts[4])
        finalize_last_swap(
            test_case=self,
            token=self.eth_token,
            token_swapped=self.lqd_token,
            account=self.testrpc_accounts[5])
        for account in self.testrpc_accounts[:4]:
            # Cancel pending .25, .16... BUY orders
            freeze_last_swap(
                test_case=self,
                account=account,
                token=self.lqd_token,
                token_swapped=self.eth_token)
            cancel_last_swap(
                test_case=self,
                account=account,
                token=self.lqd_token,
                token_swapped=self.eth_token)
            # Match none
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)

    def test_make_random_valid_swaps(self):
        for i in range(0, 2):
            print('--------------')
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

            # Match All
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)
            for account in self.testrpc_accounts[:4]:
                finalize_last_swap(
                    test_case=self,
                    token=self.eth_token,
                    token_swapped=self.lqd_token,
                    account=account)
            for account in self.testrpc_accounts[4:]:
                finalize_last_swap(
                    test_case=self,
                    token=self.lqd_token,
                    token_swapped=self.eth_token,
                    account=account)
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)

        print('--------------')
        for account in self.testrpc_accounts[:5]:
            send_swap(  # Buy LQD at 0.5 ETH
                test_case=self,
                eon_number=1,
                account=account,
                token=self.eth_token,
                token_swapped=self.lqd_token,
                amount=100,
                amount_swapped=200,
                nonce=random.randint(1, 999999))

        for account in self.testrpc_accounts[6:]:
            send_swap(  # Sell LQD at 1.0 ETH
                test_case=self,
                eon_number=1,
                account=account,
                token=self.lqd_token,
                token_swapped=self.eth_token,
                amount=100,
                amount_swapped=100,
                nonce=random.randint(1, 999999))

        # No Match
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)

        print('--------------')
        send_swap(  # Sell LQD at 0.5 ETH
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[5],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=1000,
            amount_swapped=500,
            nonce=random.randint(1, 999999))

        # One Match For All
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)
        finalize_last_swap(
            test_case=self,
            token=self.lqd_token,
            token_swapped=self.eth_token,
            account=self.testrpc_accounts[5])
        for account in self.testrpc_accounts[:5]:
            finalize_last_swap(
                test_case=self,
                token=self.eth_token,
                token_swapped=self.lqd_token,
                account=account)
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)

        print('--------------')
        send_swap(  # Buy LQD at 1.0 ETH
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=200,
            amount_swapped=200,
            nonce=random.randint(1, 999999))

        # One Match For All
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)
        finalize_last_swap(
            test_case=self,
            token=self.eth_token,
            token_swapped=self.lqd_token,
            account=self.testrpc_accounts[1])
        for account in self.testrpc_accounts[6:]:
            finalize_last_swap(
                test_case=self,
                token=self.lqd_token,
                token_swapped=self.eth_token,
                account=account)
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)

        print('--------------')
        send_swap(  # Buy LQD at 3/7 ETH (No Match / Empty)
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[1],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=3,
            amount_swapped=7,
            nonce=random.randint(1, 999999))

        send_swap(  # Sell LQD at 4/7 ETH (No Match)
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[4],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=7,
            amount_swapped=4,
            nonce=random.randint(1, 999999))

        # No Match
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)

        print('--------------')
        send_swap(  # Sell LQD at 2/7 ETH (Match with 3/7 at price of 3/7 -> Finalize both and get +1)
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[5],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=7,
            amount_swapped=2,
            nonce=random.randint(1, 999999))
        send_swap(  # Sell LQD at 1/7 ETH (No Match / Empty)
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[6],
            token=self.lqd_token,
            token_swapped=self.eth_token,
            amount=7,
            amount_swapped=1,
            nonce=random.randint(1, 999999))
        send_swap(  # Buy LQD at 4/7 ETH (Match with 1/7 at its price -> Finalize 1/7 and remain with 3 then match with 4/7 and finalize self)
            test_case=self,
            eon_number=1,
            account=self.testrpc_accounts[7],
            token=self.eth_token,
            token_swapped=self.lqd_token,
            amount=4,
            amount_swapped=7,
            nonce=random.randint(1, 999999))
        # Three Matches
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)
        # Cancel pending 4/7 sell order
        freeze_last_swap(
            test_case=self,
            account=self.testrpc_accounts[4],
            token=self.lqd_token,
            token_swapped=self.eth_token)
        cancel_last_swap(
            test_case=self,
            account=self.testrpc_accounts[4],
            token=self.lqd_token,
            token_swapped=self.eth_token)
        for account in self.testrpc_accounts[5:7]:
            finalize_last_swap(
                test_case=self,
                token=self.lqd_token,
                token_swapped=self.eth_token,
                account=account)
        finalize_last_swap(
            test_case=self,
            token=self.eth_token,
            token_swapped=self.lqd_token,
            account=self.testrpc_accounts[1])
        finalize_last_swap(
            test_case=self,
            token=self.eth_token,
            token_swapped=self.lqd_token,
            account=self.testrpc_accounts[7])
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)

        for i in range(0, 2):
            print('--------------')
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

            # Match all
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)
            for account in self.testrpc_accounts[:4]:
                finalize_last_swap(
                    test_case=self,
                    token=self.eth_token,
                    token_swapped=self.lqd_token,
                    account=account)
            for account in self.testrpc_accounts[4:]:
                finalize_last_swap(
                    test_case=self,
                    token=self.lqd_token,
                    token_swapped=self.eth_token,
                    account=account)
            confirm_swaps_for_eon(operator_eon_number=1)
            cancel_finalize_swaps_for_eon(operator_eon_number=1)
            process_swaps_for_eon(operator_eon_number=1)
