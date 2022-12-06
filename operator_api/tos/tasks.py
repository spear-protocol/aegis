import logging
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
import requests
from .models import TOSConfig

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def update_tos():
    logger.info('Updating Latest TOS')

    try:
        r = requests.get(settings.TOS_URL)

        if r.status_code != 200:
            logger.error('Invalid response status code expected 200.')
            return

        result = r.json()
    except:
        logger.error('Invalid endpoint {}.'.format(settings.TOS_URL))
        return

    if not('privacyHash' in result and 'tosHash' in result):
        logger.error('Invalid endpoint {} expecting keys "privacyHash" and ""tosHash" in response.'.format(
            settings.TOS_URL))
        return

    tos_up_to_date = TOSConfig.objects.filter(
        privacy_policy_digest__iexact=result['privacyHash'],
        terms_of_service_digest__iexact=result['tosHash']
    ).exists()

    if tos_up_to_date:
        logger.info('TOS already up to date')
        return

    TOSConfig.objects.create(
        privacy_policy_digest=result['privacyHash'], terms_of_service_digest=result['tosHash'])

    logger.info('Added New TOS')
