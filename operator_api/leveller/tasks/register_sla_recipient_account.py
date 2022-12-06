import logging
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from eth_utils import remove_0x_prefix

from admission.serializers import AdmissionRequestSerializer
from admission.tasks import process_admissions
from contractor.interfaces import LocalViewInterface
from operator_api.crypto import sign_message, encode_signature, same_hex_value
from ledger.models import Wallet, Token

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def register_sla_recipient_account():
    if same_hex_value(settings.SLA_RECIPIENT_ADDRESS, settings.HUB_OWNER_ACCOUNT_ADDRESS):
        logger.warning('Skipping registration: Hub Owner is SLA recipient.')
        return

    token = Token.objects.filter(
        address__iexact=remove_0x_prefix(settings.SLA_TOKEN_ADDRESS))

    if not token.exists():
        logger.error('SLA Payment Token not yet registered.')
        return

    if Wallet.objects.filter(token=token, address__iexact=remove_0x_prefix(settings.SLA_RECIPIENT_ADDRESS)).exists():
        logger.error('Recipient account already registered.')
        return

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    latest_eon = LocalViewInterface.latest().eon_number()

    authorization_digest = Wallet(
        token=token, address=settings.SLA_RECIPIENT_ADDRESS).get_admission_hash(latest_eon)
    authorization = sign_message(
        authorization_digest, settings.SLA_RECIPIENT_KEY)
    registration = AdmissionRequestSerializer(data={
        'token': token.address,
        'address': remove_0x_prefix(settings.SLA_RECIPIENT_ADDRESS),
        'authorization': encode_signature(authorization)
    })
    registration.is_valid(raise_exception=True)
    registration.save()
    process_admissions()
