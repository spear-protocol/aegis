import random
import multiprocessing
from rest_framework import status
from contractor.rpctestcase import RPCTestCase
from contractor.tasks import send_queued_transactions
from operator_api import testrpc_accounts
from operator_api.simulation.deposit import create_deposits
from operator_api.simulation.registration import register_testrpc_accounts, register_random_accounts
from operator_api.simulation.tokens import deploy_new_test_token, distribute_token_balance_to_addresses
from operator_api.simulation.transaction import make_random_valid_transactions, send_transaction
from operator_api.simulation.eon import commit_eon, advance_to_next_eon
from ledger.models import Token, Transfer, MinimumAvailableBalanceMarker
from ledger.token_registration import register_token
from ledger.tasks import create_checkpoint
from contractor.tasks import fully_synchronize_contract_state
from django import db


class TransactorTests(RPCTestCase):
    def test_make_random_valid_eth_transactions(self):
        eth_token = Token.objects.first()

        registered_accounts = register_testrpc_accounts(self, token=eth_token)

        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        make_random_valid_transactions(
            test_case=self,
            eon_number=1,
            accounts=registered_accounts,
            token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)

    def test_make_random_valid_erc20_transactions(self):
        eth_token = Token.objects.first()

        lqd_token_address = deploy_new_test_token(test_case=self)

        distribute_token_balance_to_addresses(
            test_case=self,
            token_address=lqd_token_address,
            recipients=testrpc_accounts.accounts)

        lqd_token = register_token(
            token_address=lqd_token_address,
            name='Liquidity',
            short_name='LQD',
            register_on_chain=True)

        send_queued_transactions()

        tokens = [
            eth_token,
            lqd_token
        ]

        registered_accounts = {
            eth_token: register_testrpc_accounts(self, token=eth_token),
            lqd_token: register_testrpc_accounts(self, token=lqd_token)
        }

        for token in tokens:
            self.assertEqual(
                self.contract_interface.get_unmanaged_funds(token.address, 1), 0)
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

        for token in tokens:
            make_random_valid_transactions(
                test_case=self,
                eon_number=1,
                accounts=registered_accounts[token],
                token=token)

        for token in tokens:
            self.assertEqual(self.contract_interface.get_unmanaged_funds(
                token.address, 1), self.contract_interface.get_total_balance(token.address))
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

    def test_non_blocking_checkpoint(self):
        eth_token = Token.objects.first()
        registered_accounts = register_testrpc_accounts(self, token=eth_token)
        register_random_accounts(self, 100, eth_token)

        create_deposits(self, registered_accounts, eth_token)

        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=2)

        # Make sure we don't miss any on-chain events
        while self.contract_interface.get_current_subblock() <= self.contract_interface.get_blocks_for_confirmation():
            self.contract_interface.do_nothing()
        # Retrieve confirmed events
        fully_synchronize_contract_state()
        while self.contract_interface.get_current_subblock() <= self.contract_interface.get_blocks_for_creation():
            self.contract_interface.do_nothing()

        # Retrieve confirmed events
        fully_synchronize_contract_state()

        checkpoint_thread = multiprocessing.Process(target=create_checkpoint)

        db.connections.close_all()
        checkpoint_thread.start()

        make_random_valid_transactions(
            test_case=self,
            eon_number=2,
            accounts=registered_accounts,
            token=eth_token,
            make_deposits=False)

        checkpoint_thread.join()
