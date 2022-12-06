import random

from django.conf import settings
from eth_utils import remove_0x_prefix

from contractor.rpctestcase import RPCTestCase
from contractor.tasks import respond_to_challenges, slash_bad_withdrawals, confirm_withdrawals
from contractor.tasks.send_queued_transactions import send_queued_transactions
from operator_api import crypto, merkle_tree, testrpc_accounts
from operator_api.merkle_tree import calculate_merkle_proof
from operator_api.simulation.deposit import create_random_deposits, make_deposit
from operator_api.simulation.withdrawal import place_parallel_withdrawals
from operator_api.simulation.eon import commit_eon, advance_to_next_eon, advance_past_slack_period, advance_past_extended_slack_period
from operator_api.simulation.epoch import confirm_on_chain_events
from operator_api.simulation.registration import register_testrpc_accounts
from operator_api.simulation.tokens import deploy_new_test_token, distribute_token_balance_to_addresses
from operator_api.simulation.swap import send_swap, freeze_last_swap, finalize_last_swap, cancel_last_swap, init_swap_challenge, freeze_swap, cancel_swap, finalize_swap
from operator_api.tx_merkle_tree import TransactionMerkleTree
from operator_api.util import cyan, long_string_to_list, csf_to_list
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Wallet, TokenCommitment, Token, RootCommitment, TokenPair, WithdrawalRequest, Withdrawal, Transfer
from ledger.tests import simulate_eon_with_random_transfers
from ledger.token_registration import register_token
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps_for_eon
from swapper.tasks.confirm_swaps import confirm_swaps_for_eon
from swapper.tasks.process_swaps import process_swaps_for_eon


class ContractorTests(RPCTestCase):
    def test_empty_state_update_challenge_responder(self):
        eth_token = Token.objects.first()
        # Initialize accounts from testrpc
        registered_accounts = register_testrpc_accounts(
            test_case=self,
            token=eth_token)
        # Do transfers, create checkpoint and broadcast it
        commit_eon(
            test_case=self,
            eon_number=1)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        simulate_eon_with_random_transfers(
            test_case=self,
            eon_number=1,
            accounts=registered_accounts,
            token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 2), 0)
        # Issue challenges
        advance_past_slack_period(test_case=self)
        for i in range(1, len(registered_accounts)):
            wallet = Wallet.objects.get(address=remove_0x_prefix(
                registered_accounts[i].get('address')))
            wallet_transfer_context = WalletTransferContext(
                wallet=wallet, transfer=None)
            active_state = wallet_transfer_context.last_appended_active_state(
                eon_number=1)
            v, r, s = active_state.operator_signature.vrs()
            tx_set_root = crypto.zfill(
                crypto.decode_hex(active_state.tx_set_hash))
            deltas = [int(active_state.updated_spendings),
                      int(active_state.updated_gains)]

            self.contract_interface.issue_state_update_challenge_empty(
                token_address=eth_token.address,
                wallet=wallet.address,
                trail_identifier=wallet.trail_identifier,
                tx_set_root=tx_set_root,
                deltas=deltas,
                r=crypto.uint256(r), s=crypto.uint256(s), v=v)
        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=2)
        self.assertEqual(live_challenges, len(registered_accounts) - 1)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)
        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()
        commit_eon(
            test_case=self,
            eon_number=2)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 3), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 3), self.contract_interface.get_total_balance(eth_token.address))
        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=2)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

    def test_state_update_challenge_responder(self):
        eth_token = Token.objects.first()
        # Initialize accounts from testrpc
        registered_accounts = register_testrpc_accounts(
            test_case=self,
            token=eth_token)
        # Do transfers, create checkpoint and broadcast it
        commit_eon(
            test_case=self,
            eon_number=1)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        simulate_eon_with_random_transfers(
            test_case=self,
            eon_number=1,
            accounts=registered_accounts,
            token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 2), 0)
        # Issue challenges
        advance_past_slack_period(test_case=self)
        last_checkpoint = self.contract_interface.get_last_checkpoint()
        previous_checkpoint = RootCommitment.objects.get(eon_number=1)

        self.assertEqual(
            crypto.hex_value(last_checkpoint[1]),
            RootCommitment.objects.get(eon_number=last_checkpoint[0]).merkle_root)

        cyan('Issue challenges in eon: {}'.format(
            self.contract_interface.get_current_eon_number()))
        skip = 0
        for i in range(1, len(registered_accounts)):
            wallet = Wallet.objects.get(
                token=eth_token,
                address=remove_0x_prefix(registered_accounts[i].get('address')))
            wallet_transfer_context = WalletTransferContext(
                wallet=wallet, transfer=None)
            balance = wallet_transfer_context.balance_as_of_eon(
                eon_number=1)
            active_state = wallet_transfer_context.last_appended_active_state(
                eon_number=1)

            if active_state is None:
                cyan('No Challenge by: {}'.format(wallet.address))
                skip += 1
                continue

            v, r, s = active_state.operator_signature.vrs()
            tx_set_root = crypto.zfill(
                crypto.decode_hex(active_state.tx_set_hash))
            deltas = [int(active_state.updated_spendings),
                      int(active_state.updated_gains)]

            self.assertEqual(len(balance.merkle_proof_hashes) % 64, 0)
            self.assertEqual(balance.eon_number, last_checkpoint[0] - 1)

            node_hash = merkle_tree.leaf_hash(
                merkle_tree.wallet_leaf_inner_hash,
                {
                    'contract': settings.HUB_LQD_CONTRACT_ADDRESS,
                    'token': eth_token.address,
                    'wallet': wallet.address,
                    'left': balance.left,
                    'right': balance.right,
                    'active_state_checksum': b'\0'*32,
                    'passive_checksum': b'\0'*32,
                    'passive_amount': 0,
                    'passive_marker': 0,
                })

            token_commitment = TokenCommitment.objects.get(
                token=balance.wallet.token,
                root_commitment__eon_number=balance.eon_number)
            self.assertEqual(self.contract_interface.check_exclusive_allotment_proof(
                allotment_trail=int(balance.merkle_proof_trail),
                membership_trail=eth_token.trail,
                node=node_hash,
                merkle_root=crypto.decode_hex(previous_checkpoint.merkle_root),
                allotment_chain=[crypto.zfill(crypto.decode_hex(v)) for v in
                                 long_string_to_list(balance.merkle_proof_hashes, 64)],
                membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                  long_string_to_list(token_commitment.membership_hashes, 64)],
                value=csf_to_list(balance.merkle_proof_values, int),
                left=int(balance.left),
                right=int(balance.right)
            ), balance.right)

            self.contract_interface.issue_state_update_challenge_merkle(
                token_address=wallet.token.address,
                wallet=wallet.address,
                active_state_checksum=b'\0' * 32,
                trail=int(balance.merkle_proof_trail),
                allotment_chain=[crypto.zfill(crypto.decode_hex(v)) for v in
                                 long_string_to_list(balance.merkle_proof_hashes, 64)],
                membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                  long_string_to_list(token_commitment.membership_hashes, 64)],
                value=csf_to_list(balance.merkle_proof_values, int),
                left=int(balance.left),
                right=int(balance.right),
                tx_set_root=tx_set_root,
                deltas=deltas,
                r=crypto.uint256(r), s=crypto.uint256(s), v=v,
                passive_checksum=b'\0'*32,
                passive_amount=0,
                passive_marker=0)

        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=2)
        self.assertEqual(live_challenges, len(registered_accounts) - 1 - skip)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)
        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()
        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=2)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

    def test_transaction_delivery_challenge_responder(self):
        eth_token = Token.objects.first()
        # Initialize accounts from testrpc
        registered_accounts = register_testrpc_accounts(
            test_case=self,
            token=eth_token)
        # Do transfers, create checkpoint and broadcast it
        commit_eon(
            test_case=self,
            eon_number=1)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        simulate_eon_with_random_transfers(
            test_case=self,
            eon_number=1,
            accounts=registered_accounts,
            token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 2), 0)
        # Issue challenges
        advance_past_slack_period(test_case=self)
        skip = 0
        for i in range(1, len(registered_accounts)):
            wallet = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
                registered_accounts[i].get('address')))
            wallet_transfer_context = WalletTransferContext(
                wallet=wallet, transfer=None)
            transfer = wallet_transfer_context.last_appended_incoming_active_transfer(
                eon_number=1)

            if transfer is None:
                cyan('No Challenge by: {}'.format(wallet.address))
                skip += 1
                continue

            sender = transfer.wallet
            sender_transfer_context = WalletTransferContext(
                wallet=sender, transfer=transfer)

            self.assertEqual(sender.address, transfer.wallet.address)
            self.assertEqual(wallet.address, transfer.recipient.address)

            transfers_list_nonce_index_map = {}
            transfers_list = sender_transfer_context.authorized_transfers_list_shorthand(
                only_appended=True,
                force_append=False,
                last_transfer_is_finalized=False,
                index_map=transfers_list_nonce_index_map)
            transfer_tree = TransactionMerkleTree(transfers_list)
            transfer_index = transfers_list_nonce_index_map.get(
                int(transfer.nonce))
            transfer_node = transfer_tree.merkle_tree_leaf_map.get(
                transfer_index)
            transfer_proof = [node.get('hash') for node in calculate_merkle_proof(
                transfer_index, transfer_node)]

            sender_active_state = sender_transfer_context.last_appended_active_state(
                eon_number=1)

            self.assertEqual(sender_active_state.tx_set_hash,
                             crypto.hex_value(transfer_tree.root_hash()))

            v, r, s = sender_active_state.operator_signature.vrs()
            tx_set_root = crypto.zfill(
                crypto.decode_hex(sender_active_state.tx_set_hash))
            deltas = [int(sender_active_state.updated_spendings),
                      int(sender_active_state.updated_gains)]

            self.assertTrue(self.contract_interface.check_merkle_membership_proof(
                trail=int(transfer_index),
                chain=[crypto.zfill(x) for x in transfer_proof],
                node=transfer_node.get('hash'),
                merkle_root=tx_set_root))

            chain_transition_checksum = self.contract_interface.check_proof_of_transition_agreement(
                token_address=wallet.token.address,
                holder=sender.address,
                trail_identifier=sender.trail_identifier,
                eon_number=1,
                tx_set_root=tx_set_root,
                deltas=deltas,
                attester=settings.HUB_OWNER_ACCOUNT_ADDRESS,
                r=crypto.uint256(r), s=crypto.uint256(s), v=v)

            self.assertEqual(
                crypto.hex_value(chain_transition_checksum),
                crypto.hex_value(sender_active_state.checksum()))

            self.contract_interface.issue_delivery_challenge(
                token_address=wallet.token.address,
                wallet=wallet.address,
                sender=sender.address,
                nonce=int(transfer.nonce),
                sender_tx_recipient_trails=[
                    sender.trail_identifier, transfer_index, transfer.recipient.trail_identifier],
                chain=[crypto.zfill(x) for x in transfer_proof],
                tx_set_root=tx_set_root,
                deltas=deltas,
                amount=int(transfer.amount),
                r=crypto.uint256(r), s=crypto.uint256(s), v=v)

        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=2)
        self.assertEqual(live_challenges, len(registered_accounts) - 1 - skip)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)
        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()
        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=2)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

    def test_withdrawal_slash_client(self):
        eth_token = Token.objects.first()
        # Initialize accounts from testrpc, commit to registrations
        registered_accounts = register_testrpc_accounts(
            test_case=self,
            token=eth_token)
        commit_eon(
            test_case=self,
            eon_number=1)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        advance_to_next_eon(
            test_case=self,
            eon_number=2)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 2), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 2), 0)
        commit_eon(
            test_case=self,
            eon_number=2)
        # Do transfers, and commit to them
        simulate_eon_with_random_transfers(
            test_case=self,
            eon_number=2,
            accounts=registered_accounts,
            token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 2), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 2), 0)
        # Issue withdrawals
        dishonest_clients = 0
        to_slash = 0
        token_commitment = TokenCommitment.objects.get(
            token=eth_token,
            root_commitment__eon_number=2)

        for i in range(1, len(registered_accounts)):
            wallet = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
                registered_accounts[i].get('address')))
            wallet_transfer_context = WalletTransferContext(
                wallet=wallet, transfer=None)
            allotment = wallet_transfer_context.balance_as_of_eon(eon_number=2)

            available_balance = wallet_transfer_context.loosely_available_funds_at_eon(
                eon_number=3,
                current_eon_number=3,
                is_checkpoint_created=True,
                only_appended=True)

            passive_checksum, passive_amount, passive_marker = wallet_transfer_context.get_passive_values(
                eon_number=1)

            dishonest = random.randint(
                0, 2) < 2 and available_balance < allotment.amount()

            honest_draw = min(available_balance, allotment.amount())
            overdraw = max(available_balance, allotment.amount())

            total_draw = overdraw if dishonest else honest_draw

            if dishonest:
                dishonest_clients += 1

            withdrawal_amounts = [total_draw // 4,
                                  total_draw // 2, total_draw // 4]

            for withdrawal_amount in withdrawal_amounts:
                if dishonest:
                    to_slash += withdrawal_amount

                cyan([dishonest, wallet.address,
                      withdrawal_amount, available_balance])

                self.contract_interface.withdraw(
                    token_address=wallet.token.address,
                    wallet=wallet.address,
                    active_state_checksum=crypto.zfill(
                        allotment.active_state_checksum()),
                    trail=int(allotment.merkle_proof_trail),
                    allotment_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                     long_string_to_list(allotment.merkle_proof_hashes, 64)],
                    membership_chain=[crypto.zfill(crypto.decode_hex(checksum)) for checksum in
                                      long_string_to_list(token_commitment.membership_hashes, 64)],
                    values=csf_to_list(allotment.merkle_proof_values, int),
                    exclusive_allotment_interval=[
                        int(allotment.left), int(allotment.right)],
                    withdrawal_amount=int(withdrawal_amount),
                    passive_checksum=passive_checksum,
                    passive_amount=passive_amount,
                    passive_marker=passive_marker)

            client_state_variables = self.contract_interface.get_client_contract_state_variables(
                wallet.token.address,
                wallet.address)

            withdrawals_on_chain = client_state_variables[6]

            self.assertTrue(len(withdrawals_on_chain)
                            == len(withdrawal_amounts))

            for i in range(len(withdrawals_on_chain)):

                pending_withdrawal = withdrawals_on_chain[i]
                withdrawal_on_chain_eon_number = pending_withdrawal[0]
                withdrawal_on_chain_amount = pending_withdrawal[1]

                self.assertEqual(withdrawal_on_chain_eon_number, 3)
                self.assertEqual(withdrawal_on_chain_amount,
                                 withdrawal_amounts[i])

        cyan('{} slashes expected, {} wei to be slashed'.format(
            dishonest_clients, to_slash))

        pre_pending_withdrawal = self.contract_interface.get_pending_withdrawals(
            eth_token.address, eon_number=3)
        cyan('PRE-SLASH Amount Pending Withdrawal On-Chain: {}'.format(pre_pending_withdrawal))
        confirm_on_chain_events(self)
        slash_bad_withdrawals()
        send_queued_transactions()
        post_pending_withdrawal = self.contract_interface.get_pending_withdrawals(
            eth_token.address, eon_number=3)
        cyan('POST-SLASH Amount Pending Withdrawal On-Chain: {}'.format(post_pending_withdrawal))

        withdrawals = WithdrawalRequest.objects.filter(
            slashed=True, eon_number__gte=1)
        self.assertEqual(len(withdrawals), dishonest_clients*3)

        self.assertEqual(post_pending_withdrawal, pre_pending_withdrawal - to_slash,
                         "Expected to slash more: {}".format((pre_pending_withdrawal - to_slash) < post_pending_withdrawal))

    def test_swap_delivery_challenge_responder(self):
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

        tp = TokenPair.objects.create(token_from=eth_token, token_to=lqd_token)
        self.assertEqual(
            tp.conduit, '3e323616eb611ee4b3006a7643e0baf6aea1c182')
        TokenPair.objects.create(token_from=lqd_token, token_to=eth_token)

        registered_accounts = {
            'eth_token': register_testrpc_accounts(self, token=eth_token),
            'lqd_token': register_testrpc_accounts(self, token=lqd_token)
        }

        for token in tokens:
            self.assertEqual(
                self.contract_interface.get_unmanaged_funds(token.address, 1), 0)
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

        make_deposit(self, eth_token,
                     registered_accounts['eth_token'][1], 1000)
        make_deposit(self, lqd_token,
                     registered_accounts['lqd_token'][2], 1000)

        confirm_on_chain_events(self)

        for token in tokens:
            self.assertEqual(
                self.contract_interface.get_unmanaged_funds(token.address, 1), 1000)
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

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

        buy_lqd = send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[1],
            token=eth_token,
            token_swapped=lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=buy_lqd_nonce)

        sell_lqd = send_swap(  # Sell LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[2],
            token=lqd_token,
            token_swapped=eth_token,
            amount=2,
            amount_swapped=1,
            nonce=sell_lqd_nonce)

        # Match All
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)
        finalize_last_swap(
            test_case=self,
            token=eth_token,
            token_swapped=lqd_token,
            account=testrpc_accounts.accounts[1])
        finalize_last_swap(
            test_case=self,
            token=lqd_token,
            token_swapped=eth_token,
            account=testrpc_accounts.accounts[2])
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        advance_to_next_eon(
            test_case=self,
            eon_number=2)
        commit_eon(
            test_case=self,
            eon_number=3)
        advance_past_slack_period(test_case=self)

        eon_number = 2

        wallet_eth = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
            testrpc_accounts.accounts[1]['address']))
        wallet_lqd = Wallet.objects.get(token=lqd_token, address=remove_0x_prefix(
            testrpc_accounts.accounts[1]['address']))

        wallet_eth_transfer_context = WalletTransferContext(
            wallet=wallet_eth, transfer=None)
        #wallet_lqd_transfer_context = WalletTransferContext(wallet=wallet_lqd, transfer=None)

        transfer_eth = wallet_eth_transfer_context.last_appended_outgoing_active_transfer(
            eon_number=eon_number)
        #transfer_lqd = wallet_lqd_transfer_context.last_appended_incoming_transfer(eon_number=eon_number)

        init_swap_challenge(self, transfer_eth, eon_number)

        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=eon_number + 1)
        self.assertEqual(live_challenges, 1)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)

        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()

        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=eon_number + 1)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

    def test_non_finalized_swap_delivery_challenge_responder(self):
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

        tp = TokenPair.objects.create(token_from=eth_token, token_to=lqd_token)
        self.assertEqual(
            tp.conduit, '3e323616eb611ee4b3006a7643e0baf6aea1c182')
        TokenPair.objects.create(token_from=lqd_token, token_to=eth_token)

        registered_accounts = {
            'eth_token': register_testrpc_accounts(self, token=eth_token),
            'lqd_token': register_testrpc_accounts(self, token=lqd_token)
        }

        for token in tokens:
            self.assertEqual(
                self.contract_interface.get_unmanaged_funds(token.address, 1), 0)
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

        make_deposit(self, eth_token,
                     registered_accounts['eth_token'][1], 1000)
        make_deposit(self, lqd_token,
                     registered_accounts['lqd_token'][2], 1000)

        confirm_on_chain_events(self)

        for token in tokens:
            self.assertEqual(
                self.contract_interface.get_unmanaged_funds(token.address, 1), 1000)
            self.assertEqual(
                self.contract_interface.get_managed_funds(token.address, 1), 0)

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

        buy_lqd = send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[1],
            token=eth_token,
            token_swapped=lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=buy_lqd_nonce)

        sell_lqd = send_swap(  # Sell LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[2],
            token=lqd_token,
            token_swapped=eth_token,
            amount=2,
            amount_swapped=1,
            nonce=sell_lqd_nonce)

        # Match All
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        advance_to_next_eon(
            test_case=self,
            eon_number=2)
        commit_eon(
            test_case=self,
            eon_number=3)
        advance_past_slack_period(test_case=self)

        eon_number = 2

        wallet_eth = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
            testrpc_accounts.accounts[1]['address']))
        wallet_lqd = Wallet.objects.get(token=lqd_token, address=remove_0x_prefix(
            testrpc_accounts.accounts[1]['address']))

        wallet_eth_transfer_context = WalletTransferContext(
            wallet=wallet_eth, transfer=None)
        #wallet_lqd_transfer_context = WalletTransferContext(wallet=wallet_lqd, transfer=None)

        transfer_eth = wallet_eth_transfer_context.last_appended_outgoing_active_transfer(
            eon_number=eon_number)
        #transfer_lqd = wallet_lqd_transfer_context.last_appended_incoming_transfer(eon_number=eon_number)

        init_swap_challenge(self, transfer_eth, eon_number)

        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=eon_number + 1)
        self.assertEqual(live_challenges, 1)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)

        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()

        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=eon_number + 1)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

    def test_withdrawal_confirmation(self):
        eth_token = Token.objects.first()
        # Initialize accounts from testrpc, commit to registrations
        registered_accounts = register_testrpc_accounts(
            test_case=self,
            token=eth_token)
        commit_eon(
            test_case=self,
            eon_number=1)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        # Make deposits, commit to them
        create_random_deposits(
            test_case=self,
            number_of_deposits=random.randint(12, 17),
            accounts=registered_accounts,
            token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        advance_to_next_eon(
            test_case=self,
            eon_number=2)
        commit_eon(
            test_case=self,
            eon_number=3)

        # Issue withdrawals
        total_amounts = {}
        total_requests = 0
        for_eon_number = 3

        for i in range(1, len(registered_accounts)):
            wallet_address = registered_accounts[i].get('address')
            total_withdraw_amount, withdrawal_amounts, overdraw = place_parallel_withdrawals(
                test_case=self,
                token=eth_token,
                wallet_address=wallet_address,
                current_eon=for_eon_number)

            total_amounts[i] = total_withdraw_amount

            if(total_withdraw_amount == 0):
                continue
            else:
                total_requests += 3

            client_state_variables = self.contract_interface.get_client_contract_state_variables(
                eth_token.address, wallet_address)

            # get only pending withdrawals from the current eon
            withdrawals_on_chain = list(
                filter(lambda w: w[0] == for_eon_number, client_state_variables[6]))

            self.assertEqual(len(withdrawal_amounts), 3)
            self.assertEqual(len(withdrawals_on_chain),
                             len(withdrawal_amounts))

            self.assertTrue(len(withdrawals_on_chain)
                            == len(withdrawal_amounts))

            for i in range(len(withdrawals_on_chain)):

                pending_withdrawal = withdrawals_on_chain[i]
                withdrawal_on_chain_amount = pending_withdrawal[1]

                self.assertEqual(withdrawal_on_chain_amount,
                                 withdrawal_amounts[i])

        confirm_on_chain_events(self)

        withdrawals = WithdrawalRequest.objects.filter(
            slashed=False, eon_number=for_eon_number)
        self.assertEqual(len(withdrawals),  total_requests)

        advance_to_next_eon(
            test_case=self,
            eon_number=3)
        commit_eon(
            test_case=self,
            eon_number=4)

        for i in range(1, len(registered_accounts)):
            wallet = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
                registered_accounts[i].get('address')))
            amount = self.contract_interface.get_confirmed_withdrawable_amount(
                eth_token.address, wallet.address)
            
            self.assertEqual(amount, 0)

        advance_to_next_eon(
            test_case=self,
            eon_number=4)
        commit_eon(
            test_case=self,
            eon_number=5)
        advance_past_extended_slack_period(self)

        for i in range(1, len(registered_accounts)):
            wallet = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
                registered_accounts[i].get('address')))
            amount = self.contract_interface.get_confirmed_withdrawable_amount(
                eth_token.address, wallet.address)
            
            self.assertEqual(amount, total_amounts[i])

        confirm_withdrawals()
        send_queued_transactions()

        confirm_on_chain_events(self)

        for i in range(1, len(registered_accounts)):
            if(total_amounts[i] == 0):
                continue

            wallet = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
                            registered_accounts[i].get('address')))
            confirmed_withdrawals = Withdrawal.objects.filter(
                wallet=wallet, eon_number=5)
            self.assertEqual(len(confirmed_withdrawals), 3)

            confirmed_withdrawals_amount = 0

            for confirmed_withdrawal in confirmed_withdrawals:
                confirmed_withdrawals_amount += confirmed_withdrawal.amount

            self.assertEqual(confirmed_withdrawals_amount, total_amounts[i])


    def test_withdrawal_parallel_confirmation(self):
        eth_token = Token.objects.first()
        # Initialize accounts from testrpc, commit to registrations
        registered_accounts = register_testrpc_accounts(
            test_case=self,
            token=eth_token)
        commit_eon(
            test_case=self,
            eon_number=1)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), 0)
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)
        # Make deposits, commit to them
        create_random_deposits(
            test_case=self,
            number_of_deposits=random.randint(12, 17),
            accounts=registered_accounts,
            token=eth_token)
        self.assertEqual(self.contract_interface.get_unmanaged_funds(
            eth_token.address, 1), self.contract_interface.get_total_balance(eth_token.address))
        self.assertEqual(self.contract_interface.get_managed_funds(
            eth_token.address, 1), 0)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        advance_to_next_eon(
            test_case=self,
            eon_number=2)
        commit_eon(
            test_case=self,
            eon_number=3)

        # Issue withdrawals
        total_amounts = {}
        total_requests = 0
        for_eon_number = 3

        for i in range(1, len(registered_accounts)):
            wallet_address = registered_accounts[i].get('address')
            total_withdraw_amount, withdrawal_amounts, overdraw = place_parallel_withdrawals(
                test_case=self,
                token=eth_token,
                wallet_address=wallet_address,
                current_eon=for_eon_number)

            total_amounts[i] = total_withdraw_amount

            if(total_withdraw_amount == 0):
                continue
            else:
                total_requests += 3

            client_state_variables = self.contract_interface.get_client_contract_state_variables(
                eth_token.address, wallet_address)

            # get only pending withdrawals from the current eon
            withdrawals_on_chain = list(
                filter(lambda w: w[0] == for_eon_number, client_state_variables[6]))

            self.assertEqual(len(withdrawal_amounts), 3)
            self.assertEqual(len(withdrawals_on_chain),
                             len(withdrawal_amounts))

            self.assertTrue(len(withdrawals_on_chain)
                            == len(withdrawal_amounts))

            for i in range(len(withdrawals_on_chain)):

                pending_withdrawal = withdrawals_on_chain[i]
                withdrawal_on_chain_amount = pending_withdrawal[1]

                self.assertEqual(withdrawal_on_chain_amount,
                                 withdrawal_amounts[i])

        confirm_on_chain_events(self)

        withdrawals = WithdrawalRequest.objects.filter(
            slashed=False, eon_number=for_eon_number)
        self.assertEqual(len(withdrawals),  total_requests)

        advance_to_next_eon(
            test_case=self,
            eon_number=3)
        commit_eon(
            test_case=self,
            eon_number=4)

        advance_to_next_eon(
            test_case=self,
            eon_number=4)
        commit_eon(
            test_case=self,
            eon_number=5)

        # issue more withdrawals
        total_amounts_2 = {}
        total_requests_2 = 0
        for_eon_number = 5

        for i in range(1, len(registered_accounts)):
            wallet_address = registered_accounts[i].get('address')
            total_withdraw_amount, withdrawal_amounts, overdraw = place_parallel_withdrawals(
                test_case=self,
                token=eth_token,
                wallet_address=wallet_address,
                current_eon=for_eon_number)

            total_amounts_2[i] = total_withdraw_amount

            if(total_withdraw_amount == 0):
                continue
            else:
                total_requests_2 += 3

            client_state_variables = self.contract_interface.get_client_contract_state_variables(
                eth_token.address, wallet_address)

            # get only pending withdrawals from the current eon
            withdrawals_on_chain = list(
                filter(lambda w: w[0] == for_eon_number, client_state_variables[6]))

            self.assertEqual(len(withdrawal_amounts), 3)
            self.assertEqual(len(withdrawals_on_chain),
                             len(withdrawal_amounts))

            for i in range(len(withdrawals_on_chain)):

                pending_withdrawal = withdrawals_on_chain[i]
                withdrawal_on_chain_amount = pending_withdrawal[1]

                self.assertEqual(withdrawal_on_chain_amount,
                                 withdrawal_amounts[i])

        confirm_on_chain_events(self)

        withdrawals = WithdrawalRequest.objects.filter(
            slashed=False, eon_number=for_eon_number)
        self.assertEqual(len(withdrawals), total_requests_2)

        advance_to_next_eon(
            test_case=self,
            eon_number=5)
        commit_eon(
            test_case=self,
            eon_number=6)

        for i in range(1, len(registered_accounts)):
            if(total_amounts[i] == 0):
                continue

            wallet = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
                registered_accounts[i].get('address')))
            amount = self.contract_interface.get_confirmed_withdrawable_amount(
                eth_token.address, wallet.address)
            self.assertEqual(total_amounts[i], amount)

            requests = WithdrawalRequest.objects.filter(
                wallet=wallet, slashed=False, withdrawal__isnull=True).order_by('id')
            self.assertEqual(len(requests), 6)

            self.contract_interface.confirm_withdrawals(
                eth_token.address, wallet.address)
            confirm_on_chain_events(self)

            confirmed_withdrawals = Withdrawal.objects.filter(
                wallet=wallet, eon_number=6)
            self.assertEqual(len(confirmed_withdrawals), 3)

            confirmed_withdrawals_amount = 0

            for confirmed_withdrawal in confirmed_withdrawals:
                confirmed_withdrawals_amount += confirmed_withdrawal.amount

            self.assertEqual(confirmed_withdrawals_amount, amount)

            requests = WithdrawalRequest.objects.filter(
                wallet=wallet, slashed=False, withdrawal__isnull=True).order_by('id')
            self.assertEqual(len(requests), 3)

        advance_to_next_eon(
            test_case=self,
            eon_number=6)
        commit_eon(
            test_case=self,
            eon_number=7)

        advance_to_next_eon(
            test_case=self,
            eon_number=7)
        commit_eon(
            test_case=self,
            eon_number=8)

        for i in range(1, len(registered_accounts)):
            if(total_amounts_2[i] == 0):
                continue

            wallet = Wallet.objects.get(token=eth_token, address=remove_0x_prefix(
                registered_accounts[i].get('address')))
            amount = self.contract_interface.get_confirmed_withdrawable_amount(
                eth_token.address, wallet.address)
            self.assertEqual(total_amounts_2[i], amount)

            requests = WithdrawalRequest.objects.filter(
                wallet=wallet, slashed=False, withdrawal__isnull=True).order_by('id')
            self.assertEqual(len(requests), 3)

            self.contract_interface.confirm_withdrawals(
                eth_token.address, wallet.address)
            confirm_on_chain_events(self)

            confirmed_withdrawals = Withdrawal.objects.filter(
                wallet=wallet, eon_number=8)
            self.assertEqual(len(confirmed_withdrawals), 3)

            confirmed_withdrawals_amount = 0

            for confirmed_withdrawal in confirmed_withdrawals:
                confirmed_withdrawals_amount += confirmed_withdrawal.amount

            self.assertEqual(confirmed_withdrawals_amount, amount)

            requests = WithdrawalRequest.objects.filter(
                wallet=wallet, slashed=False, withdrawal__isnull=True).order_by('id')
            self.assertEqual(len(requests), 0)

    def test_multi_eon_swap_not_matched_challenge_responder(self):
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

        registered_accounts = {
            'eth_token': register_testrpc_accounts(self, token=eth_token),
            'lqd_token': register_testrpc_accounts(self, token=lqd_token)
        }

        make_deposit(self, eth_token,
                     registered_accounts['eth_token'][1], 1000)
        make_deposit(self, lqd_token,
                     registered_accounts['lqd_token'][2], 1000)

        confirm_on_chain_events(self)

        TokenPair.objects.create(token_from=eth_token, token_to=lqd_token)
        TokenPair.objects.create(token_from=lqd_token, token_to=eth_token)

        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        total_remaining_eons = 5
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[1],
            token=eth_token,
            token_swapped=lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=random.randint(1, 999999),
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=eth_token).order_by('id')[0]
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
        for i in range(3, 7):
            # proceed to next eon
            advance_to_next_eon(
                test_case=self,
                eon_number=i-1)
            commit_eon(
                test_case=self,
                eon_number=i)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i)
            cancel_finalize_swaps_for_eon(operator_eon_number=i)
            process_swaps_for_eon(operator_eon_number=i)

            swap = Transfer.objects.get(
                swap=True, tx_id=swap_tx_id, eon_number=i-1)

            advance_past_slack_period(test_case=self)
            init_swap_challenge(self, swap, i-1)

            # Assert challenges are alive
            live_challenges = self.contract_interface.get_live_challenge_count(
                eon_number=i)
            self.assertEqual(live_challenges, 1)
            cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
            confirm_on_chain_events(self)

            # Respond to challenges
            respond_to_challenges()
            send_queued_transactions()

            # Assert challenges are dead
            live_challenges = self.contract_interface.get_live_challenge_count(
                eon_number=i)
            cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
            self.assertEqual(live_challenges, 0)

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i, False), wallet_funds_before)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i, False), recipient_funds_before)

        commit_eon(test_case=self, eon_number=i)

    def test_multi_eon_swap_not_finalized_challenge_responder(self):
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

        registered_accounts = {
            'eth_token': register_testrpc_accounts(self, token=eth_token),
            'lqd_token': register_testrpc_accounts(self, token=lqd_token)
        }

        make_deposit(self, eth_token,
                     registered_accounts['eth_token'][1], 1000)
        make_deposit(self, lqd_token,
                     registered_accounts['lqd_token'][2], 1000)

        confirm_on_chain_events(self)

        TokenPair.objects.create(token_from=eth_token, token_to=lqd_token)
        TokenPair.objects.create(token_from=lqd_token, token_to=eth_token)

        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        total_remaining_eons = 5
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[1],
            token=eth_token,
            token_swapped=lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=random.randint(1, 999999),
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=eth_token).order_by('id')[0]
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
            account=testrpc_accounts.accounts[2],
            token=lqd_token,
            token_swapped=eth_token,
            amount=2,
            amount_swapped=1,
            nonce=random.randint(1, 999999),
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        # finalize opposite swap
        finalize_last_swap(
            test_case=self,
            token=lqd_token,
            token_swapped=eth_token,
            account=testrpc_accounts.accounts[2],
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=5)
        self.assertTrue(swap.complete)

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

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=6)
        cancel_finalize_swaps_for_eon(operator_eon_number=6)
        process_swaps_for_eon(operator_eon_number=6)

        advance_past_slack_period(test_case=self)
        init_swap_challenge(self, swap, 5)

        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=6)
        self.assertEqual(live_challenges, 1)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)

        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()

        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=6)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

        advance_to_next_eon(test_case=self, eon_number=6)
        commit_eon(test_case=self, eon_number=7)

    def test_multi_eon_swap_finalized_challenge_responder(self):
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

        registered_accounts = {
            'eth_token': register_testrpc_accounts(self, token=eth_token),
            'lqd_token': register_testrpc_accounts(self, token=lqd_token)
        }

        make_deposit(self, eth_token,
                     registered_accounts['eth_token'][1], 1000)
        make_deposit(self, lqd_token,
                     registered_accounts['lqd_token'][2], 1000)

        confirm_on_chain_events(self)

        TokenPair.objects.create(token_from=eth_token, token_to=lqd_token)
        TokenPair.objects.create(token_from=lqd_token, token_to=eth_token)

        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        total_remaining_eons = 5
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[1],
            token=eth_token,
            token_swapped=lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=random.randint(1, 999999),
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=eth_token).order_by('id')[0]
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
            account=testrpc_accounts.accounts[2],
            token=lqd_token,
            token_swapped=eth_token,
            amount=2,
            amount_swapped=1,
            nonce=random.randint(1, 999999),
            eon_count=1)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        # finalize opposite swap
        finalize_last_swap(
            test_case=self,
            token=lqd_token,
            token_swapped=eth_token,
            account=testrpc_accounts.accounts[2],
            eon_count=1)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=5)
        # finalize swap
        finalize_swap(
            test_case=self,
            swap=swap,
            account=testrpc_accounts.accounts[1],
            eon_count=total_remaining_eons)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=5)
        cancel_finalize_swaps_for_eon(operator_eon_number=5)
        process_swaps_for_eon(operator_eon_number=5)

        self.assertEqual(wallet_transfer_context.available_funds_at_eon(
            5, False), wallet_funds_before - 1)
        self.assertEqual(recipient_transfer_context.available_funds_at_eon(
            5, False), recipient_funds_before + 2)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=5)
        self.assertTrue(swap.complete)

        # proceed to next eon
        advance_to_next_eon(
            test_case=self,
            eon_number=5)
        commit_eon(
            test_case=self,
            eon_number=6)

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=6)
        cancel_finalize_swaps_for_eon(operator_eon_number=6)
        process_swaps_for_eon(operator_eon_number=6)

        advance_past_slack_period(test_case=self)
        init_swap_challenge(self, swap, 5)

        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=6)
        self.assertEqual(live_challenges, 1)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)

        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()

        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=6)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

        advance_to_next_eon(test_case=self, eon_number=6)
        commit_eon(test_case=self, eon_number=7)

    def test_multi_eon_swap_partially_matched_challenge_responder(self):
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

        registered_accounts = {
            'eth_token': register_testrpc_accounts(self, token=eth_token),
            'lqd_token': register_testrpc_accounts(self, token=lqd_token)
        }

        make_deposit(self, eth_token, registered_accounts['eth_token'][1], 100)
        make_deposit(self, lqd_token, registered_accounts['lqd_token'][2], 100)

        confirm_on_chain_events(self)

        TokenPair.objects.create(token_from=eth_token, token_to=lqd_token)
        TokenPair.objects.create(token_from=lqd_token, token_to=eth_token)

        wallet_transfer_context = WalletTransferContext(
            wallet=Wallet.objects.get(address__iexact=remove_0x_prefix(testrpc_accounts.accounts[1].get('address')), token=eth_token), transfer=None)
        recipient_transfer_context = WalletTransferContext(
            wallet=Wallet.objects.get(address__iexact=remove_0x_prefix(testrpc_accounts.accounts[1].get('address')), token=lqd_token), transfer=None)

        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        total_remaining_eons = 6
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[1],
            token=eth_token,
            token_swapped=lqd_token,
            amount=4,
            amount_swapped=8,
            nonce=random.randint(1, 999999),
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=eth_token).order_by('id')[0]
        swap_tx_id = swap.tx_id

        wallet_funds_before = 4
        recipient_funds_before = 0

        # process swaps
        confirm_swaps_for_eon(operator_eon_number=2)
        cancel_finalize_swaps_for_eon(operator_eon_number=2)
        process_swaps_for_eon(operator_eon_number=2)

        # skip some eons
        for i in range(3, 7):
            send_swap(  # Buy LQD at 0.5 ETH
                test_case=self,
                eon_number=i-1,
                account=testrpc_accounts.accounts[2],
                token=lqd_token,
                token_swapped=eth_token,
                amount=2,
                amount_swapped=1,
                nonce=random.randint(1, 999999),
                eon_count=1)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i-1)
            cancel_finalize_swaps_for_eon(operator_eon_number=i-1)
            process_swaps_for_eon(operator_eon_number=i-1)

            # finalize opposite swap
            finalize_last_swap(
                test_case=self,
                token=lqd_token,
                token_swapped=eth_token,
                account=testrpc_accounts.accounts[2],
                eon_count=1)

            # process swaps
            confirm_swaps_for_eon(operator_eon_number=i-1)
            cancel_finalize_swaps_for_eon(operator_eon_number=i-1)
            process_swaps_for_eon(operator_eon_number=i-1)

            wallet_funds_before -= 1
            recipient_funds_before += 2

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i-1, False), wallet_funds_before)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i-1, False), recipient_funds_before)

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

            swap = Transfer.objects.get(
                swap=True, tx_id=swap_tx_id, eon_number=i-1)
            self.assertFalse(swap.voided)

            print("EON {}".format(i))
            advance_past_slack_period(test_case=self)
            init_swap_challenge(self, swap, i-1)

            # Assert challenges are alive
            live_challenges = self.contract_interface.get_live_challenge_count(
                eon_number=i)
            self.assertEqual(live_challenges, 1)
            cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
            confirm_on_chain_events(self)

            # Respond to challenges
            respond_to_challenges()
            send_queued_transactions()

            # Assert challenges are dead
            live_challenges = self.contract_interface.get_live_challenge_count(
                eon_number=i)
            cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
            self.assertEqual(live_challenges, 0)

            self.assertEqual(wallet_transfer_context.available_funds_at_eon(
                i, False), wallet_funds_before)
            self.assertEqual(recipient_transfer_context.available_funds_at_eon(
                i, False), recipient_funds_before)

        commit_eon(test_case=self, eon_number=i)

    def test_multi_eon_swap_cancelled_challenge_responder(self):
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

        registered_accounts = {
            'eth_token': register_testrpc_accounts(self, token=eth_token),
            'lqd_token': register_testrpc_accounts(self, token=lqd_token)
        }

        make_deposit(self, eth_token, registered_accounts['eth_token'][1], 100)
        make_deposit(self, lqd_token, registered_accounts['lqd_token'][2], 100)

        confirm_on_chain_events(self)

        TokenPair.objects.create(token_from=eth_token, token_to=lqd_token)
        TokenPair.objects.create(token_from=lqd_token, token_to=eth_token)

        wallet_transfer_context = WalletTransferContext(
            wallet=Wallet.objects.get(address__iexact=remove_0x_prefix(testrpc_accounts.accounts[1].get('address')), token=eth_token), transfer=None)
        recipient_transfer_context = WalletTransferContext(
            wallet=Wallet.objects.get(address__iexact=remove_0x_prefix(testrpc_accounts.accounts[1].get('address')), token=lqd_token), transfer=None)

        commit_eon(
            test_case=self,
            eon_number=1)

        advance_to_next_eon(
            test_case=self,
            eon_number=1)
        commit_eon(
            test_case=self,
            eon_number=2)

        total_remaining_eons = 6
        # make persistent swap
        send_swap(  # Buy LQD at 0.5 ETH
            test_case=self,
            eon_number=2,
            account=testrpc_accounts.accounts[1],
            token=eth_token,
            token_swapped=lqd_token,
            amount=1,
            amount_swapped=2,
            nonce=random.randint(1, 999999),
            eon_count=total_remaining_eons)

        swap = Transfer.objects.filter(
            swap=True, wallet__token=eth_token).order_by('id')[0]
        swap_tx_id = swap.tx_id

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

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=4)
        freeze_swap(
            test_case=self,
            swap=swap,
            account=testrpc_accounts.accounts[1])
        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=4)
        cancel_swap(
            test_case=self,
            swap=swap,
            account=testrpc_accounts.accounts[1],
            eon_count=total_remaining_eons)

        swap = Transfer.objects.get(
            swap=True, tx_id=swap_tx_id, eon_number=4)
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

        advance_past_slack_period(test_case=self)
        init_swap_challenge(self, swap, 4)

        # Assert challenges are alive
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=5)
        self.assertEqual(live_challenges, 1)
        cyan('PRE-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        confirm_on_chain_events(self)

        # Respond to challenges
        respond_to_challenges()
        send_queued_transactions()

        # Assert challenges are dead
        live_challenges = self.contract_interface.get_live_challenge_count(
            eon_number=5)
        cyan('POST-ANSWER Live Challenges On-Chain: {}'.format(live_challenges))
        self.assertEqual(live_challenges, 0)

        advance_to_next_eon(
            test_case=self,
            eon_number=5)
        commit_eon(test_case=self, eon_number=6)
