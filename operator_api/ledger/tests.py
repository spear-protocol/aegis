import random

from eth_utils import remove_0x_prefix

from contractor.rpctestcase import RPCTestCase
from contractor.tasks import send_queued_transactions
from operator_api import testrpc_accounts
from operator_api.simulation.deposit import create_random_deposits, create_deposits
from operator_api.simulation.eon import simulate_eon_with_random_transfers, advance_to_next_eon
from operator_api.simulation.epoch import commit_eon
from operator_api.simulation.registration import register_testrpc_accounts
from operator_api.simulation.swap import send_swap, finalize_last_swap, cancel_last_swap, freeze_last_swap
from operator_api.simulation.tokens import deploy_new_test_token, distribute_token_balance_to_addresses
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Token, Transfer, Wallet, TokenPair
from ledger.token_registration import register_token
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps_for_eon
from swapper.tasks.confirm_swaps import confirm_swaps_for_eon
from swapper.tasks.process_swaps import process_swaps_for_eon


class LedgerTests(RPCTestCase):
    def test_transfer_processor_task(self):
        self.eth_token = Token.objects.first()

        commit_eon(
            test_case=self,
            eon_number=1)

        registered_accounts = register_testrpc_accounts(
            self, token=self.eth_token)

        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            self.eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            self.eth_token.address, 1), 0)
        simulate_eon_with_random_transfers(
            test_case=self,
            eon_number=1,
            accounts=registered_accounts,
            token=self.eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            self.eth_token.address, 1), self.contract_interface.get_total_balance(self.eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            self.eth_token.address, 1), 0)

        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            self.eth_token.address, 2), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            self.eth_token.address, 2), self.contract_interface.get_total_balance(self.eth_token.address))
        new_deposits = create_random_deposits(
            test_case=self,
            number_of_deposits=random.randint(12, 17),
            accounts=registered_accounts,
            token=self.eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            self.eth_token.address, 2), new_deposits)
        self.assertEqual(self.contract_interface.get_managed_funds(self.eth_token.address, 2),
                         self.contract_interface.get_total_balance(self.eth_token.address) - new_deposits)

    def test_checkpoint_creation(self):
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

        for account in testrpc_accounts.accounts[1:5]:
            eth_wallet = Wallet.objects.get(address=remove_0x_prefix(
                account.get('address')), token=self.eth_token)
            lqd_wallet = Wallet.objects.get(address=remove_0x_prefix(
                account.get('address')), token=self.lqd_token)

            eth_wallet_context = WalletTransferContext(
                wallet=eth_wallet, transfer=None)
            lqd_wallet_context = WalletTransferContext(
                wallet=lqd_wallet, transfer=None)

            account['reduced_eth_balance'] = eth_wallet_context.available_funds_at_eon(
                eon_number=1, only_appended=False) - 1
            account['reduced_lqd_balance'] = lqd_wallet_context.available_funds_at_eon(
                eon_number=1, only_appended=False)

            send_swap(  # Buy LQD at 0.5 ETH
                test_case=self,
                eon_number=1,
                account=account,
                token=self.eth_token,
                token_swapped=self.lqd_token,
                amount=1,
                amount_swapped=2,
                nonce=random.randint(1, 999999))

        for account in testrpc_accounts.accounts[5:9]:
            eth_wallet = Wallet.objects.get(address=remove_0x_prefix(
                account.get('address')), token=self.eth_token)
            lqd_wallet = Wallet.objects.get(address=remove_0x_prefix(
                account.get('address')), token=self.lqd_token)

            eth_wallet_context = WalletTransferContext(
                wallet=eth_wallet, transfer=None)
            lqd_wallet_context = WalletTransferContext(
                wallet=lqd_wallet, transfer=None)

            account['reduced_eth_balance'] = eth_wallet_context.available_funds_at_eon(
                eon_number=1, only_appended=False)
            account['reduced_lqd_balance'] = lqd_wallet_context.available_funds_at_eon(
                eon_number=1, only_appended=False) - 2

            send_swap(  # Sell LQD at 0.5 ETH
                test_case=self,
                eon_number=1,
                account=account,
                token=self.lqd_token,
                token_swapped=self.eth_token,
                amount=2,
                amount_swapped=1,
                nonce=random.randint(1, 999999))

        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)
        for account in testrpc_accounts.accounts[1:5]:
            finalize_last_swap(
                test_case=self,
                token=self.eth_token,
                token_swapped=self.lqd_token,
                account=account)
        for account in testrpc_accounts.accounts[5:9]:
            finalize_last_swap(
                test_case=self,
                token=self.lqd_token,
                token_swapped=self.eth_token,
                account=account)
        confirm_swaps_for_eon(operator_eon_number=1)
        cancel_finalize_swaps_for_eon(operator_eon_number=1)
        process_swaps_for_eon(operator_eon_number=1)

        buyers_sellers = [
            testrpc_accounts.accounts[1:5],
            testrpc_accounts.accounts[5:9]
        ]
        for i in range(0, 2):
            for account in buyers_sellers[i]:
                eth_wallet = Wallet.objects.get(address=remove_0x_prefix(
                    account.get('address')), token=self.eth_token)
                lqd_wallet = Wallet.objects.get(address=remove_0x_prefix(
                    account.get('address')), token=self.lqd_token)

                eth_wallet_context = WalletTransferContext(
                    wallet=eth_wallet, transfer=None)
                lqd_wallet_context = WalletTransferContext(
                    wallet=lqd_wallet, transfer=None)

                eth_out, eth_in = eth_wallet_context.off_chain_actively_sent_received_amounts(
                    eon_number=1, only_appended=False)
                lqd_out, lqd_in = lqd_wallet_context.off_chain_actively_sent_received_amounts(
                    eon_number=1, only_appended=False)

                eth_out -= account['reduced_eth_balance']
                lqd_out -= account['reduced_lqd_balance']

                if i == 0:  # LQD buyers
                    assert eth_out == 1 and eth_in == 0, '{}/{}'.format(
                        eth_out, eth_in)
                    assert lqd_out - 2 == 0 and lqd_in - 2 == 2, '{}/{}'.format(
                        lqd_out, lqd_in)
                else:  # LQD sellers
                    assert lqd_out == 2 and lqd_in == 0, '{}/{}'.format(
                        lqd_out, lqd_in)
                    assert eth_out - 1 == 0 and eth_in - 1 == 1, '{}/{}'.format(
                        eth_out, eth_in)

        # Verify transfers were complete
        swaps = Transfer.objects.filter(swap=True)
        for transfer in swaps:
            self.assertTrue(transfer.is_fulfilled_swap())

        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)

        commit_eon(
            test_case=self,
            eon_number=2)
