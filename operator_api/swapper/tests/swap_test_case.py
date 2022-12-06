import random

from contractor.rpctestcase import RPCTestCase
from contractor.tasks import send_queued_transactions
from operator_api import testrpc_accounts
from operator_api.simulation.deposit import create_deposits
from operator_api.simulation.registration import register_testrpc_accounts
from operator_api.simulation.tokens import deploy_new_test_token, distribute_token_balance_to_addresses
from ledger.models import Token, TokenPair
from ledger.token_registration import register_token


class SwapTestCase(RPCTestCase):
    def setUp(self):
        super(SwapTestCase, self).setUp()
        self.eth_token = Token.objects.first()

        lqd_token_address = deploy_new_test_token(test_case=self)

        distribute_token_balance_to_addresses(
            test_case=self,
            token_address=lqd_token_address,
            recipients=testrpc_accounts.accounts)

        self.lqd_token = register_token(
            token_address=lqd_token_address,
            name='Liquidity',
            short_name='LQD',
            register_on_chain=True)

        send_queued_transactions()

        self.tokens = [
            self.eth_token,
            self.lqd_token
        ]

        TokenPair.objects.create(
            token_from=self.eth_token, token_to=self.lqd_token)
        TokenPair.objects.create(
            token_from=self.lqd_token, token_to=self.eth_token)

        self.registered_accounts = {
            self.eth_token: register_testrpc_accounts(self, token=self.eth_token),
            self.lqd_token: register_testrpc_accounts(
                self, token=self.lqd_token)
        }

        for token in self.tokens:
            self.assertEqual(
                self.contract_interface.get_unmanaged_funds(token.address, 1), 0)
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

        for token in self.tokens:
            create_deposits(self, testrpc_accounts.accounts, token)

        for token in self.tokens:
            self.assertEqual(self.contract_interface.get_unmanaged_funds(
                token.address, 1), self.contract_interface.get_total_balance(token.address))
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

        # remove hub account (used to remove extra funds) and last account (top make them even) to make list size 8
        self.testrpc_accounts = testrpc_accounts.accounts[1:-1]
