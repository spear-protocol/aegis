from django.conf import settings
import rlp

from contractor.interfaces.nocust_contract_interface import token_contract_abi
from contractor.rpctestcase import RPCTestCase
from operator_api import util
from eth_utils import keccak, decode_hex, add_0x_prefix


def deploy_new_test_token(test_case: RPCTestCase):
    nonce = test_case.contract_interface.web3.eth.getTransactionCount(
        settings.HUB_OWNER_ACCOUNT_ADDRESS)

    token_address = keccak(rlp.encode(
        [decode_hex(settings.HUB_OWNER_ACCOUNT_ADDRESS), nonce]))[12:]
    print('Token address: {}'.format(
        test_case.contract_interface.web3.toChecksumAddress(token_address)))

    util.just_deploy(
        bytecode_file='../just-deploy/contracts/ethereum-token-contract-1',
        private_key=settings.HUB_OWNER_ACCOUNT_KEY)

    return test_case.contract_interface.web3.toChecksumAddress(token_address)


def distribute_token_balance_to_addresses(test_case: RPCTestCase, token_address, recipients):
    total_balance = test_case.contract_interface.get_onchain_address_balance(
        account_address=settings.HUB_OWNER_ACCOUNT_ADDRESS,
        token_address=token_address)

    amount = total_balance // (len(recipients) + 1)

    token_contract = test_case.contract_interface.web3.eth.contract(
        address=add_0x_prefix(token_address),
        abi=token_contract_abi)

    for recipient in recipients:
        tx = token_contract\
            .functions\
            .transfer(test_case.contract_interface.web3.toChecksumAddress(recipient.get('address')), amount)\
            .transact({'from': settings.HUB_OWNER_ACCOUNT_ADDRESS})

        print('Transfer at {} for {} of {} to {}'.format(
            test_case.contract_interface.get_transaction_receipt(
                tx).get('blockNumber'),
            amount,
            token_address,
            recipient.get('address')))
