from celery import shared_task
from asgiref.sync import async_to_sync
from django.conf import settings
import requests
from channels.layers import get_channel_layer
from celery.utils.log import get_task_logger
import logging
from contractor.interfaces import EthereumInterface
from django.core.cache import cache

channel_layer = get_channel_layer()
logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


# task to send post request to hook
@shared_task
def trigger_hook(data):
    if settings.NOTIFICATION_HOOK_URL is not None:
        chain_id = cache.get_or_set(
            'chain_id', EthereumInterface().get_chain_id())
        data['operator'] = "{}-{}".format(
            settings.HUB_LQD_CONTRACT_ADDRESS, chain_id)
        try:
            req = requests.post(
                settings.NOTIFICATION_HOOK_URL,
                data=data
            )
            req.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error("Failed to trigger hook: {}".format(e))
