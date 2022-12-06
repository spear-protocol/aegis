import traceback
from celery.utils.log import get_task_logger

from contractor.rpctestcase import RPCTestCase
from operator_api.crypto import random_wei
from operator_api.simulation.epoch import confirm_on_chain_events
import random

from operator_api.util import cyan
from ledger.models import Token

logger = get_task_logger(__name__)


def make_deposit(test_case: RPCTestCase, token, wallet, amount):
    try:
        tx = test_case.contract_interface.deposit(
            token_address=token.address,
            wallet=wallet.get('address'),
            amount=amount)
        print('Deposit at {} for {}'.format(
            test_case.contract_interface.get_transaction_receipt(tx).get('blockNumber'), amount))
        return amount
    except:
        logger.error('Could not perform deposit of {} from {}'.format(
            amount, wallet.get('address')))
        traceback.print_exc()
        return 0


def create_random_deposits(test_case: RPCTestCase, number_of_deposits, accounts, token: Token):
    cyan('Creating {} random deposits'.format(number_of_deposits))
    deposited = 0
    for _ in range(number_of_deposits):
        random_wallet = accounts[random.randint(0, len(accounts) - 1)]
        amount = random_wei()
        deposited += make_deposit(test_case, token, random_wallet, amount)

    confirm_on_chain_events(test_case)

    return deposited


def create_deposits(test_case: RPCTestCase, accounts, token: Token):
    cyan('Creating deposits')
    deposited = 0
    for account in accounts:
        amount = random_wei()
        deposited += make_deposit(test_case, token, account, amount)

    confirm_on_chain_events(test_case)

    return deposited
