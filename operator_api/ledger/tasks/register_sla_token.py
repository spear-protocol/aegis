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
def register_sla_token():
    if Token.objects.filter(address__iexact=remove_0x_prefix(settings.SLA_TOKEN_ADDRESS)).exists():
        logger.error('SLA token already registered.')
        return

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    logger.warning('Registering SLA Token')

    register_token(
        token_address=settings.SLA_TOKEN_ADDRESS,
        name='LQD',
        short_name='LQD',
        register_on_chain=True)
