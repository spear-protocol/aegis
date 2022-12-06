from .swap_test_case import SwapTestCase
from operator_api.simulation.swap import send_swap, finalize_swap
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps_for_eon
from swapper.tasks.confirm_swaps import confirm_swaps_for_eon
from swapper.tasks.process_swaps import process_swaps_for_eon
from operator_api.simulation.eon import commit_eon, advance_to_next_eon

from ledger.models import Transfer
import random


class BuySellSemanticsSwapTests(SwapTestCase):
    def setUp(self):
        super(BuySellSemanticsSwapTests, self).setUp()
        self.eon_number = 1
        commit_eon(
            test_case=self,
            eon_number=self.eon_number)

    def tearDown(self):
        # make sure checkpont is successful
        advance_to_next_eon(
            test_case=self,
            eon_number=self.eon_number)
        commit_eon(
            test_case=self,
            eon_number=self.eon_number+1)
        super(BuySellSemanticsSwapTests, self).tearDown()

    def make_order(self, account, is_primary_lqd, is_sell, amount, price):
        if is_sell:
            amount = amount
            amount_swapped = amount*price
            self.assertEqual(amount_swapped//price, amount)
        else:
            amount_swapped = amount
            amount = amount*price
            self.assertEqual(amount//price, amount_swapped)

        if is_primary_lqd:
            primary_token = self.lqd_token
            secondary_token = self.eth_token
        else:
            secondary_token = self.lqd_token
            primary_token = self.eth_token

        nonce = random.randint(1, 999999)
        send_swap(
            test_case=self,
            eon_number=self.eon_number,
            account=account,
            token=primary_token,
            token_swapped=secondary_token,
            amount=int(amount),
            amount_swapped=int(amount_swapped),
            nonce=nonce,
            sell_order=is_sell)
        process_swaps_for_eon(operator_eon_number=self.eon_number)
        return nonce

    def get_order(self, nonce):
        order = Transfer.objects.get(eon_number=self.eon_number, nonce=nonce)
        return (order, *order.matched_amounts(all_eons=True))

    def test_sell_sell(self):
        # sell LQD at 0.25 ETH
        sell_order_lqd_0_25_nonce = self.make_order(
            account=self.testrpc_accounts[1],
            is_primary_lqd=True,
            is_sell=True,
            amount=20,
            price=0.25
        )

        # sell ETH at 5 LQD
        # LQD at 0.2 ETH
        self.make_order(
            account=self.testrpc_accounts[2],
            is_primary_lqd=False,
            is_sell=True,
            amount=5,
            price=5
        )

        sell_order_lqd_0_25, matched_out, matched_in = self.get_order(
            nonce=sell_order_lqd_0_25_nonce
        )

        self.assertEqual(matched_out, 0)
        self.assertEqual(matched_in, 0)
        self.assertFalse(sell_order_lqd_0_25.complete)

        # sell ETH at 2 LQD
        # LQD at 0.5 ETH
        sell_order_eth_2_nonce = self.make_order(
            account=self.testrpc_accounts[3],
            is_primary_lqd=False,
            is_sell=True,
            amount=4,
            price=2
        )

        sell_order_lqd_0_25, matched_out, matched_in = self.get_order(
            nonce=sell_order_lqd_0_25_nonce
        )
        self.assertEqual(matched_out, 16)
        self.assertEqual(matched_in, 4)
        self.assertFalse(sell_order_lqd_0_25.complete)

        sell_order_eth_2, matched_out, matched_in = self.get_order(
            nonce=sell_order_eth_2_nonce
        )
        self.assertEqual(matched_out, 4)
        self.assertEqual(matched_in, 16)
        self.assertTrue(sell_order_eth_2.complete)

        # sell ETH at 2 LQD
        # LQD at 0.5 ETH
        sell_order_eth_2_nonce = self.make_order(
            account=self.testrpc_accounts[4],
            is_primary_lqd=False,
            is_sell=True,
            amount=1,
            price=2
        )

        sell_order_lqd_0_25, matched_out, matched_in = self.get_order(
            nonce=sell_order_lqd_0_25_nonce
        )
        self.assertEqual(matched_out, 20)
        self.assertEqual(matched_in, 5)
        self.assertTrue(sell_order_lqd_0_25.complete)

        sell_order_eth_2, matched_out, matched_in = self.get_order(
            nonce=sell_order_eth_2_nonce
        )
        self.assertEqual(matched_out, 1)
        self.assertEqual(matched_in, 4)
        self.assertTrue(sell_order_eth_2.complete)

    def test_sell_buy(self):
        # sell ETH at 3 LQD
        sell_order_eth_3_nonce = self.make_order(
            account=self.testrpc_accounts[1],
            is_primary_lqd=False,
            is_sell=True,
            amount=20,
            price=3
        )

        # buy ETH at 4 LQD
        buy_order_eth_4_nonce = self.make_order(
            account=self.testrpc_accounts[2],
            is_primary_lqd=True,
            is_sell=False,
            amount=10,
            price=4
        )

        buy_order_eth_4, matched_out, matched_in = self.get_order(
            nonce=buy_order_eth_4_nonce
        )
        self.assertEqual(matched_out, 30)
        self.assertEqual(matched_in, 10)
        self.assertTrue(buy_order_eth_4.complete)

        sell_order_eth_3, matched_out, matched_in = self.get_order(
            nonce=sell_order_eth_3_nonce
        )
        self.assertEqual(matched_out, 10)
        self.assertEqual(matched_in, 30)
        self.assertFalse(sell_order_eth_3.complete)

    # this is a trivial case
    # default behaviour of our matcher handles this case
    # def test_buy_sell(self):

    def test_buy_buy(self):
        # buy ETH at 4 LQD
        buy_order_eth_4_nonce = self.make_order(
            account=self.testrpc_accounts[1],
            is_primary_lqd=True,
            is_sell=False,
            amount=10,
            price=4
        )

        # buy LQD at 0.5 ETH
        # ETH at 2 LQD
        buy_order_lqd_0_5_nonce = self.make_order(
            account=self.testrpc_accounts[2],
            is_primary_lqd=False,
            is_sell=False,
            amount=20,
            price=0.5
        )

        buy_order_eth_4, matched_out, matched_in = self.get_order(
            nonce=buy_order_eth_4_nonce
        )
        self.assertEqual(matched_out, 20)
        self.assertEqual(matched_in, 5)
        self.assertFalse(buy_order_eth_4.complete)

        buy_order_lqd_0_5, matched_out, matched_in = self.get_order(
            nonce=buy_order_lqd_0_5_nonce
        )
        self.assertEqual(matched_out, 5)
        self.assertEqual(matched_in, 20)
        self.assertTrue(buy_order_lqd_0_5.complete)

        # buy LQD at 0.5 ETH
        # ETH at 2 LQD
        buy_order_lqd_0_5_nonce = self.make_order(
            account=self.testrpc_accounts[3],
            is_primary_lqd=False,
            is_sell=False,
            amount=20,
            price=0.5
        )

        buy_order_eth_4, matched_out, matched_in = self.get_order(
            nonce=buy_order_eth_4_nonce
        )
        self.assertEqual(matched_out, 40)
        self.assertEqual(matched_in, 10)
        self.assertTrue(buy_order_eth_4.complete)

        buy_order_lqd_0_5, matched_out, matched_in = self.get_order(
            nonce=buy_order_lqd_0_5_nonce
        )
        self.assertEqual(matched_out, 5)
        self.assertEqual(matched_in, 20)
        self.assertTrue(buy_order_lqd_0_5.complete)
