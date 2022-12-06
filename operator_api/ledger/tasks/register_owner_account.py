import logging

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from eth_utils import remove_0x_prefix

from admission.serializers import AdmissionRequestSerializer
from admission.tasks import process_admissions
from contractor.interfaces import LocalViewInterface
from operator_api.crypto import sign_message, encode_signature, hex_value
from ledger.models import Wallet, Token
from tos.models import TOSConfig

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def register_owner_account(token: Token):
    if Wallet.objects.filter(token=token, address__iexact=remove_0x_prefix(settings.HUB_OWNER_ACCOUNT_ADDRESS)).exists():
        logger.error('Owner account already registered.')
        return

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    logger.warning('Registering owner account: {}'.format(
        settings.HUB_OWNER_ACCOUNT_ADDRESS))

    latest_eon_number = LocalViewInterface.latest().eon_number()

    authorization_digest = Wallet(
        token=token, address=settings.HUB_OWNER_ACCOUNT_ADDRESS).get_admission_hash(latest_eon_number)
    authorization = sign_message(
        authorization_digest, settings.HUB_OWNER_ACCOUNT_KEY)
    latest_tos_config = TOSConfig.objects.all().order_by('time').last()
    tos_signature = sign_message(
        hex_value(latest_tos_config.digest()), settings.HUB_OWNER_ACCOUNT_KEY)
    registration = AdmissionRequestSerializer(data={
        'token': token.address,
        'address': remove_0x_prefix(settings.HUB_OWNER_ACCOUNT_ADDRESS),
        'authorization': {
            'value': encode_signature(authorization)
        },
        'tos_signature': {
            'value': encode_signature(tos_signature)
        }
    })
    registration.is_valid(raise_exception=True)
    registration.save()
    process_admissions()
