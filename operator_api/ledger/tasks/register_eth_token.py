import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from eth_utils import remove_0x_prefix

from contractor.interfaces import LocalViewInterface
from contractor.models import ContractLedgerState
from ledger.models import Token
from ledger.token_registration import register_token

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def register_eth_token():
    if Token.objects.filter(address__iexact=remove_0x_prefix(settings.HUB_LQD_CONTRACT_ADDRESS)).exists():
        logger.error('ETH token already registered.')
        return

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    logger.warning('Registering ETH Token')

    eth_token = register_token(
        token_address=settings.HUB_LQD_CONTRACT_ADDRESS,
        name='Ethereum',
        short_name='ETH',
        register_on_chain=False)

    ContractLedgerState.objects.create(
        contract_state=LocalViewInterface.genesis(),
        token=eth_token,
        pending_withdrawals=0,
        confirmed_withdrawals=0,
        deposits=0,
        total_balance=0)
