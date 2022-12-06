import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from ledger.models import Token, TokenPair
from django.conf import settings
from eth_utils import remove_0x_prefix

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def whitelist_default_token_pairs():
    try:
        eth_token = Token.objects.get(
            address__iexact=remove_0x_prefix(settings.HUB_LQD_CONTRACT_ADDRESS))
        sla_token = Token.objects.get(
            address__iexact=remove_0x_prefix(settings.SLA_TOKEN_ADDRESS))

        tokens = [eth_token, sla_token]

        for token_from in tokens:
            for token_to in tokens:
                if token_from.id != token_to.id:
                    tp, created = TokenPair.objects.get_or_create(
                        token_from=token_from, token_to=token_to)
                    if created:
                        logger.info("Whitelisted {}(0x{}) ---> {}(0x{}) with conduit: {}".format(
                            tp.token_from.short_name, tp.token_from.address,
                            tp.token_to.short_name,  tp.token_to.short_name,
                            tp.conduit
                        ))
                    else:
                        logger.info("Skipping whitelisting {}(0x{}) ---> {}(0x{})), pair already added".format(
                            tp.token_from.short_name, tp.token_from.address,
                            tp.token_to.short_name,  tp.token_to.short_name
                        ))

    except Token.DoesNotExist:
        logger.error("SLA/ETH token is not registered")
