import logging
from celery.utils.log import get_task_logger
from celery import shared_task
from django.conf import settings

from contractor.interfaces import EthereumInterface

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def check_eth_level():
    logger.info('Checking owner account balance..')
    remaining_balance = EthereumInterface().get_account_balance(
        settings.HUB_OWNER_ACCOUNT_ADDRESS)

    if remaining_balance < settings.OWNER_BALANCE_THRESHOLD:
        logger.error('Owner Account Balance is below threshold, {} < {} weis\n'.format(
            remaining_balance, settings.OWNER_BALANCE_THRESHOLD))
    else:
        logger.info('Owner account has enough fuel\n')
