import logging
import traceback
import time

from django.conf import settings
from django.db.models import Max
from eth_utils import add_0x_prefix, remove_0x_prefix, decode_hex
from contractor.abi import load_abi
from contractor.interfaces import LocalViewInterface
from contractor.models import ChallengeEntry, ContractState, EthereumTransaction, ContractLedgerState
from operator_api.crypto import same_hex_value
from ledger.models import WithdrawalRequest, Challenge, Token, RootCommitment
from .ethereum_interface import EthereumInterface
from celery.utils.log import get_task_logger
from operator_api import crypto

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)

nocust_contract_abi = load_abi('NOCUSTCommitChain.json')
token_contract_abi = load_abi('ERC20.json')


# class NOCUSTInterface(EthereumInterface, metaclass=Singleton):
class NOCUSTContractInterface(EthereumInterface):
    def __init__(self):
        super(NOCUSTContractInterface, self).__init__()
        self.contract = self.web3.eth.contract(
            address=settings.HUB_LQD_CONTRACT_ADDRESS,
            abi=nocust_contract_abi)
        self.web3.eth.defaultAccount = settings.HUB_OWNER_ACCOUNT_ADDRESS
        # self.web3.eth.enable_unaudited_features()

    def queue_transaction_by_owner(self, transaction, tag):
        latest_remote_nonce = self.web3.eth.getTransactionCount(
            settings.HUB_OWNER_ACCOUNT_ADDRESS)
        with EthereumTransaction.global_lock():
            latest_local_nonce = 0
            if EthereumTransaction.objects\
                    .filter(from_address=remove_0x_prefix(settings.HUB_OWNER_ACCOUNT_ADDRESS))\
                    .exists():
                latest_local_nonce = EthereumTransaction.objects \
                    .filter(from_address=remove_0x_prefix(settings.HUB_OWNER_ACCOUNT_ADDRESS)) \
                    .aggregate(Max('nonce')) \
                    .get('nonce__max') + 1

            transaction_nonce = max(
                latest_remote_nonce,
                latest_local_nonce)

            logger.info('Queuing TX #{}'.format(transaction_nonce))



            transaction_dictionary = transaction.buildTransaction({
                'chainId': self.web3.net.version,
                'from': settings.HUB_OWNER_ACCOUNT_ADDRESS,
                'gas': 5000000,
                'gasPrice': self.web3.toWei('25', 'gwei'),
                'nonce': transaction_nonce
            })

            return EthereumTransaction.objects.create(
                chain_id=transaction_dictionary.get('chainId'),
                from_address=remove_0x_prefix(
                    settings.HUB_OWNER_ACCOUNT_ADDRESS),
                to_address=remove_0x_prefix(transaction_dictionary.get('to')),
                gas=transaction_dictionary.get('gas'),
                data=remove_0x_prefix(transaction_dictionary.get('data')),
                value=transaction_dictionary.get('value'),
                nonce=transaction_dictionary.get('nonce'),
                tag=tag)

    def sign_for_delivery_as_owner(self, transaction: EthereumTransaction, gas_price: int):
        transaction_dictionary = {
            'chainId': transaction.chain_id,
            'from': add_0x_prefix(transaction.from_address),
            'to': add_0x_prefix(transaction.to_address),
            'gas': 2 * transaction.gas,
            'gasPrice': gas_price,
            'data': add_0x_prefix(transaction.data),
            'value': int(transaction.value),
            'nonce': transaction.nonce}
        logger.info('Signing TX Dict: {}'.format(transaction_dictionary))
        return self.web3.eth.account.signTransaction(
            transaction_dict=transaction_dictionary,
            private_key=settings.HUB_OWNER_ACCOUNT_KEY)

    # def send_signed_transaction_by_owner(self, transaction):
    #     logger.warning('Sending tx with gas: {}'.format(transaction.estimateGas() + 100000))
    #     txn = transaction.buildTransaction({
    #         'gas': transaction.estimateGas() + 150000, # TODO measure this more finely
    #         'gasPrice': self.web3.toWei('125', 'gwei'), # TODO dynamic, replace by fee
    #         'nonce': self.web3.eth.getTransactionCount(settings.HUB_OWNER_ACCOUNT_ADDRESS)
    #     })
    #     signed_txn = self.web3.eth.account.signTransaction(txn, private_key=settings.HUB_OWNER_ACCOUNT_KEY)
    #     return self.send_raw_transaction(signed_txn.rawTransaction)

    def get_logs(self, block):
        logs = super(NOCUSTContractInterface, self).get_logs(block)
        return [log for log in logs if log.get(u'address').lower() == settings.HUB_LQD_CONTRACT_ADDRESS.lower()]

    def get_last_checkpoint_submission_eon(self, block_identifier='latest'):
        return self.contract \
            .functions\
            .lastSubmissionEon()\
            .call(block_identifier=block_identifier)

    def get_last_checkpoint(self, block_identifier='latest'):
        eon_number = self.get_last_checkpoint_submission_eon()
        eons_kept = LocalViewInterface.get_contract_parameters().eons_kept
        return self.contract\
            .functions\
            .getCheckpointAtSlot(eon_number % eons_kept)\
            .call(block_identifier=block_identifier)

    def get_is_checkpoint_submitted_for_current_eon(self, block_identifier='latest'):
        return self.get_last_checkpoint_submission_eon(block_identifier=block_identifier) == self.get_current_eon_number(block_identifier=block_identifier)

    def do_nothing(self):
        time.sleep(0.1)
        return self.web3.manager.request_blocking("evm_mine", [])

    def queue_submit_checkpoint(self, checkpoint: RootCommitment):
        return self.queue_transaction_by_owner(
            transaction=self.contract.functions.submitCheckpoint(
                decode_hex(checkpoint.basis),
                decode_hex(checkpoint.merkle_root)),
            tag=checkpoint.tag())

    def get_has_missed_checkpoint_submission(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .hasMissedCheckpointSubmission()\
            .call(block_identifier=block_identifier)

    def deposit(self, token_address, wallet, amount):
        if same_hex_value(token_address, settings.HUB_LQD_CONTRACT_ADDRESS):
            return self.contract\
                .functions\
                .deposit(add_0x_prefix(token_address), add_0x_prefix(wallet), amount)\
                .transact({'from': wallet, 'value': amount})
        else:
            token_contract = self.web3.eth.contract(
                address=add_0x_prefix(token_address),
                abi=token_contract_abi)

            token_contract\
                .functions\
                .approve(settings.HUB_LQD_CONTRACT_ADDRESS, amount)\
                .transact({'from': wallet})

            return self.contract\
                .functions\
                .deposit(add_0x_prefix(token_address), add_0x_prefix(wallet), amount)\
                .transact({'from': wallet})

    # confirm pending withdrawals for a specific wallet-token pair
    def confirm_withdrawals(self, token_address, wallet_address):
        txid = self.contract \
            .functions \
            .confirmWithdrawal(
                add_0x_prefix(token_address),
                add_0x_prefix(wallet_address)
            ) \
            .transact({
                'from': add_0x_prefix(wallet_address),
                'gasPrice': self.get_challenge_min_gas_cost()})

        return txid

    # simulate pending withdrawal confirmation call to get total amount confirmed
    def get_confirmed_withdrawable_amount(self, token_address, wallet_address, block_identifier='latest'):
        amount = self.contract \
            .functions \
            .confirmWithdrawal(
                add_0x_prefix(token_address),
                add_0x_prefix(wallet_address)
            ) \
            .call(block_identifier=block_identifier)
        return amount

    def withdraw(self, token_address, wallet, active_state_checksum, trail, allotment_chain, membership_chain, values, exclusive_allotment_interval, withdrawal_amount, passive_checksum, passive_amount, passive_marker):
        return self.contract\
            .functions\
            .requestWithdrawal(
                add_0x_prefix(token_address),
                [
                    active_state_checksum,
                    passive_checksum
                ],
                trail,
                allotment_chain,
                membership_chain,
                values,
                [
                    exclusive_allotment_interval,
                    [passive_amount, passive_marker]
                ],
                withdrawal_amount
            )\
            .transact({
                'from': add_0x_prefix(wallet),
                'value': 100100 * self.get_challenge_min_gas_cost(),
                'gasPrice': self.get_challenge_min_gas_cost()})

    def delegated_withdraw(self, token_address, wallet_address, amount, expiry, r, s, v):
        return self.contract.functions.requestDelegatedWithdrawal(
            add_0x_prefix(token_address),
            add_0x_prefix(wallet_address),
            amount,
            expiry,
            r,
            s,
            v
        )

    def get_pending_withdrawals(self, token_address, eon_number, block_identifier='latest'):
        eons_kept = LocalViewInterface.get_contract_parameters().eons_kept
        aggregate_eon, aggregate_value = self.contract\
            .functions\
            .getPendingWithdrawalsAtSlot(add_0x_prefix(token_address), eon_number % eons_kept)\
            .call(block_identifier=block_identifier)

        return aggregate_value if aggregate_eon == eon_number else 0

    def get_confirmed_withdrawals(self, token_address, eon_number, block_identifier='latest'):
        eons_kept = LocalViewInterface.get_contract_parameters().eons_kept
        aggregate_eon, aggregate_value = self.contract\
            .functions\
            .getConfirmedWithdrawalsAtSlot(add_0x_prefix(token_address), eon_number % eons_kept)\
            .call(block_identifier=block_identifier)

        return aggregate_value if aggregate_eon == eon_number else 0

    def get_deposits(self, token_address, eon_number, block_identifier='latest'):
        eons_kept = LocalViewInterface.get_contract_parameters().eons_kept
        aggregate_eon, aggregate_value = self.contract\
            .functions\
            .getDepositsAtSlot(add_0x_prefix(token_address), eon_number % eons_kept)\
            .call(block_identifier=block_identifier)

        return aggregate_value if aggregate_eon == eon_number else 0

    def get_total_balance(self, token_address, block_identifier='latest'):
        return self.get_onchain_address_balance(settings.HUB_LQD_CONTRACT_ADDRESS, token_address, block_identifier)

    def get_onchain_address_balance(self, account_address, token_address, block_identifier='latest'):
        if remove_0x_prefix(token_address) == remove_0x_prefix(account_address):
            return self.web3\
                .eth\
                .getBalance(account_address, block_identifier=block_identifier)

        token_contract = self.web3.eth.contract(
            address=add_0x_prefix(token_address),
            abi=token_contract_abi)

        return token_contract\
            .functions\
            .balanceOf(account_address)\
            .call(block_identifier=block_identifier)

    def register_ERC20(self, token_address):
        return self.queue_transaction_by_owner(
            transaction=self.contract.functions.registerERC20(
                add_0x_prefix(token_address)),
            tag='registerERC20_{}'.format(add_0x_prefix(token_address)))

    def get_challenge_min_gas_cost(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .MIN_CHALLENGE_GAS_COST()\
            .call(block_identifier=block_identifier)

    def get_slack_period(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .BLOCKS_PER_EPOCH()\
            .call(block_identifier=block_identifier)

    def get_extended_slack_period(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .EXTENDED_BLOCKS_PER_EPOCH()\
            .call(block_identifier=block_identifier)

    def get_live_challenge_count(self, eon_number, block_identifier='latest'):
        return self.contract\
            .functions\
            .getLiveChallenges(eon_number)\
            .call(block_identifier=block_identifier)

    def issue_state_update_challenge_merkle(
            self, token_address, wallet, active_state_checksum, trail, allotment_chain, membership_chain, value, left, right, tx_set_root, deltas, r, s, v, passive_checksum, passive_amount, passive_marker):
        method = self.contract\
            .functions\
            .challengeStateUpdateWithProofOfExclusiveBalanceAllotment(
                add_0x_prefix(token_address),
                [
                    active_state_checksum,
                    passive_checksum
                ],
                trail,
                allotment_chain,
                membership_chain,
                value,
                [
                    [left, right],
                    deltas,
                    [passive_amount, passive_marker]
                ],
                [
                    r,
                    s,
                    tx_set_root
                ],
                v)
        gas_cost = method.estimateGas({
            'from': add_0x_prefix(wallet),
            'value': self.get_challenge_min_gas_cost() * 10000000})
        return method.transact({
            'from': add_0x_prefix(wallet),
            'value': self.get_challenge_min_gas_cost() * gas_cost,
            'gasPrice': self.get_challenge_min_gas_cost()})

    def issue_state_update_challenge_empty(self, token_address, wallet, trail_identifier, tx_set_root, deltas, r, s, v):
        method = self.contract\
            .functions\
            .challengeStateUpdateWithProofOfActiveStateUpdateAgreement(
                add_0x_prefix(token_address),
                tx_set_root,
                trail_identifier,
                deltas,
                r,
                s,
                v)
        gas_cost = method.estimateGas({
            'from': add_0x_prefix(wallet),
            'value': self.get_challenge_min_gas_cost() * 10000000})
        return method .transact({
            'from': add_0x_prefix(wallet),
            'value': self.get_challenge_min_gas_cost() * (gas_cost + 25),
            'gasPrice': self.get_challenge_min_gas_cost()})

    def issue_delivery_challenge(self, token_address, wallet, sender, nonce, sender_tx_recipient_trails, chain, tx_set_root, deltas, amount, r, s, v):
        wallet = add_0x_prefix(wallet)
        sender = add_0x_prefix(sender)

        method = self.contract\
            .functions\
            .challengeTransferDeliveryWithProofOfActiveStateUpdateAgreement(
                add_0x_prefix(token_address),
                [sender, wallet],
                [nonce, amount],
                sender_tx_recipient_trails,
                chain,
                deltas,
                [
                    r,
                    s,
                    tx_set_root,
                ],
                v)
        gas_cost = method.estimateGas({
            'from': wallet,
            'value': self.get_challenge_min_gas_cost() * 10000000})
        return method.transact({
            'from': wallet,
            'value': self.get_challenge_min_gas_cost()*gas_cost,
            'gasPrice': self.get_challenge_min_gas_cost()})

    # swap_order = [sell, buy, balance, nonce]
    def issue_swap_challenge(self, token_pair, wallet, swap_order, sender_tx_recipient_trails, allotment_chain, membership_chain, tx_chain, values, l_r, tx_set_root, deltas, passive_checksum, passive_amount, passive_marker):
        wallet = add_0x_prefix(wallet)
        method = self.contract\
            .functions\
            .challengeSwapEnactmentWithProofOfActiveStateUpdateAgreement(
                [
                    add_0x_prefix(token_pair[0]),
                    add_0x_prefix(token_pair[1])
                ],
                sender_tx_recipient_trails,
                allotment_chain,
                membership_chain,
                tx_chain,
                values,
                [
                    l_r,
                    deltas,
                    [passive_amount, passive_marker]
                ],
                swap_order,
                [
                    tx_set_root,
                    passive_checksum,
                    crypto.uint256(0)  # always zero
                ])
        gas_cost = method.estimateGas({
            'from': wallet,
            'value': self.get_challenge_min_gas_cost() * 10000000})
        return method.transact({
            'from': wallet,
            'value': self.get_challenge_min_gas_cost()*gas_cost,
            'gasPrice': self.get_challenge_min_gas_cost()})

    def queue_answer_state_update_challenge(self, challenge: Challenge, allotment_chain, membership_chain, values, l_r, tx_set_root, deltas, r, s, v, passive_checksum, passive_amount, passive_marker):
        return self.queue_transaction_by_owner(
            transaction=self.contract.functions.answerStateUpdateChallenge(
                add_0x_prefix(challenge.wallet.token.address),
                add_0x_prefix(challenge.wallet.address),
                allotment_chain,
                membership_chain,
                values,
                [
                    l_r,
                    deltas,
                    [passive_amount, passive_marker]
                ],
                [
                    r[0], s[0],
                    r[1], s[1],
                    tx_set_root,
                    passive_checksum
                ],
                v),
            tag=challenge.tag(0))

    def queue_answer_delivery_challenge(self, challenge: Challenge, tx_trail, allotment_chain, membership_chain, values, l_r, deltas, tx_set_root, tx_chain, passive_checksum, passive_amount, passive_marker):
        return self.queue_transaction_by_owner(
            transaction=self.contract.functions.answerTransferDeliveryChallengeWithProofOfActiveStateUpdateAgreement(
                add_0x_prefix(challenge.wallet.token.address),
                [add_0x_prefix(challenge.wallet.address),
                 add_0x_prefix(challenge.recipient.address)],
                tx_trail,
                allotment_chain,
                membership_chain,
                values,
                [
                    l_r,
                    deltas,
                    [passive_amount, passive_marker]
                ],
                [
                    tx_set_root,
                    passive_checksum
                ],
                tx_chain),
            tag=challenge.tag(tx_trail))

    def queue_answer_swap_challenge(self, challenge: Challenge, token_pair, balance_at_start_of_eon, tx_trail, allotment_chain, membership_chain, values, l_r, deltas, tx_set_root, tx_chain, passive_checksum, passive_amount, passive_marker):
        return self.queue_transaction_by_owner(
            transaction=self.contract.functions.answerSwapChallengeWithProofOfExclusiveBalanceAllotment(
                [
                    add_0x_prefix(token_pair[0]),
                    add_0x_prefix(token_pair[1])
                ],
                add_0x_prefix(challenge.wallet.address),
                tx_trail,
                allotment_chain,
                membership_chain,
                tx_chain,
                values,
                [
                    l_r,
                    deltas,
                    [passive_amount, passive_marker]
                ],
                balance_at_start_of_eon,
                [
                    tx_set_root,
                    passive_checksum,
                    crypto.uint256(0)  # always zero
                ]
            ),
            tag=challenge.tag(tx_trail))

    # queue a transaction to slash withdrawals for a wallet-token pair
    # tag used to track transaction
    def queue_slash_withdrawal(self, token_address, wallet_address, eon_number, available, r, s, v, tag):
        return self.queue_transaction_by_owner(
            transaction=self.contract.functions.slashWithdrawalWithProofOfMinimumAvailableBalance(
                add_0x_prefix(token_address),
                add_0x_prefix(wallet_address),
                [eon_number, available],
                [r, s],
                v),
            tag=tag)

    # queue a transaction to confirm withdrawals for a wallet-token pair
    # tag used to track transaction
    def queue_confirm_withdrawal(self, token_address, wallet_address, tag):
        return self.queue_transaction_by_owner(
            transaction=self.contract.functions.confirmWithdrawal(
                add_0x_prefix(token_address), add_0x_prefix(wallet_address)),
            tag=tag)

    def get_genesis_block(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .genesis()\
            .call(block_identifier=block_identifier)

    def get_current_eon_number(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .currentEon()\
            .call(block_identifier=block_identifier)

    def get_current_subblock(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .currentEra()\
            .call(block_identifier=block_identifier)

    def get_client_contract_state_variables(self, token_address, member, block_identifier='latest'):
        return self.contract\
            .functions\
            .getClientContractStateVariables(add_0x_prefix(token_address), add_0x_prefix(member))\
            .call(block_identifier=block_identifier)

    def get_challenge_record(self, token_address, recipient, sender, block_identifier='latest') -> ChallengeEntry:
        on_chain_record = self.contract\
            .functions\
            .getChallenge(add_0x_prefix(token_address), add_0x_prefix(sender), add_0x_prefix(recipient))\
            .call(block_identifier=block_identifier)
        return ChallengeEntry(on_chain_record)

    def get_blocks_per_eon(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .BLOCKS_PER_EON()\
            .call(block_identifier=block_identifier)

    def get_eons_kept(self, block_identifier='latest'):
        return self.contract\
            .functions\
            .EONS_KEPT()\
            .call(block_identifier=block_identifier)

    def get_blocks_for_confirmation(self):
        return settings.HUB_LQD_CONTRACT_CONFIRMATIONS

    def get_blocks_for_creation(self):
        return 2 * self.get_blocks_for_confirmation()

    def get_blocks_for_submission(self):
        return self.get_blocks_for_creation() + 5

    def get_basis(self, eon_number, block_identifier='latest'):
        eons_kept = LocalViewInterface.get_contract_parameters().eons_kept
        return self.contract\
            .functions\
            .getParentChainAccumulatorAtSlot(eon_number % eons_kept)\
            .call(block_identifier=block_identifier)

    def check_exclusive_allotment_proof(self, allotment_trail, membership_trail, node, merkle_root, allotment_chain, membership_chain, value, left, right, block_identifier='latest'):
        return self.contract\
            .functions\
            .verifyProofOfExclusiveBalanceAllotment(allotment_trail, membership_trail, node, merkle_root, allotment_chain, membership_chain, value, [left, right])\
            .call(block_identifier=block_identifier)

    def check_merkle_membership_proof(self, trail, chain, node, merkle_root, block_identifier='latest'):
        return self.contract\
            .functions\
            .verifyProofOfMembership(trail, chain, node, merkle_root)\
            .call(block_identifier=block_identifier)

    def check_proof_of_transition_agreement(self, token_address, holder, trail_identifier, eon_number, tx_set_root, deltas, attester, r, s, v, block_identifier='latest'):
        return self.contract\
            .functions\
            .verifyProofOfActiveStateUpdateAgreement(
                add_0x_prefix(token_address),
                add_0x_prefix(holder),
                trail_identifier,
                eon_number,
                tx_set_root,
                deltas,
                add_0x_prefix(attester),
                r,
                s,
                v)\
            .call(block_identifier=block_identifier)

    def fetch_contract_state_at_block(self, block_number):
        try:
            local_params = LocalViewInterface.get_contract_parameters()
            current_eon = 1 + \
                (block_number - local_params.genesis_block) // local_params.blocks_per_eon

            contract_state_variables = self.contract\
                .functions\
                .getServerContractStateVariables()\
                .call(block_identifier=block_number)

            basis = contract_state_variables[0]
            last_checkpoint_submission_eon = contract_state_variables[1]
            last_checkpoint = contract_state_variables[2]
            is_checkpoint_submitted_for_current_eon = contract_state_variables[3]
            has_missed_checkpoint_submission = contract_state_variables[4]
            live_challenge_count = contract_state_variables[5]

        except Exception as exception:
            traceback.print_exc()
            logger.error(
                'Could not query contract state: {}'.format(str(exception)))
            return None

        contract_state = ContractState(
            block=block_number,
            confirmed=False,
            basis=crypto.hex_value(basis),
            last_checkpoint_submission_eon=last_checkpoint_submission_eon,
            last_checkpoint=crypto.hex_value(last_checkpoint),
            is_checkpoint_submitted_for_current_eon=is_checkpoint_submitted_for_current_eon,
            has_missed_checkpoint_submission=has_missed_checkpoint_submission,
            live_challenge_count=live_challenge_count)

        contract_ledger_states = []
        for token in Token.objects.all():
            if token.block >= block_number:
                continue

            try:
                contract_state_ledger_variables = self.contract\
                    .functions\
                    .getServerContractLedgerStateVariables(current_eon, add_0x_prefix(token.address))\
                    .call(block_identifier=block_number)

                pending_withdrawals = contract_state_ledger_variables[0]
                confirmed_withdrawals = contract_state_ledger_variables[1]
                deposits = contract_state_ledger_variables[2]
                total_balance = contract_state_ledger_variables[3]

                contract_ledger_states.append(ContractLedgerState(
                    token=token,
                    pending_withdrawals=pending_withdrawals,
                    confirmed_withdrawals=confirmed_withdrawals,
                    deposits=deposits,
                    total_balance=total_balance))
            except Exception as exception:
                traceback.print_exc()
                logger.error('Could not query contract ledger state for {}: {}'.format(
                    token.address, str(exception)))
                contract_ledger_states.append(ContractLedgerState(
                    token=token,
                    pending_withdrawals=0,
                    confirmed_withdrawals=0,
                    deposits=0,
                    total_balance=0))

        return contract_state, contract_ledger_states

    def get_unmanaged_funds(self, token_address, eon_number):
        pending_withdrawal_in_last_eon = 0
        if eon_number > 0:
            pending_withdrawal_in_last_eon = self.get_pending_withdrawals(
                token_address, eon_number - 1)
        deposited_this_eon = self.get_deposits(token_address, eon_number)

        return pending_withdrawal_in_last_eon + deposited_this_eon

    def get_managed_funds(self, token_address, eon_number):
        return self.get_total_balance(token_address) - self.get_unmanaged_funds(token_address, eon_number)
