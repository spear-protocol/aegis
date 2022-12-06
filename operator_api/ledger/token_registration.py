import logging

from django.conf import settings
from eth_utils import remove_0x_prefix, decode_hex

from admission.serializers import AdmissionRequestSerializer
from contractor.interfaces import NOCUSTContractInterface, LocalViewInterface
from operator_api.crypto import sign_message, encode_signature, same_hex_value
from ledger.models import Token, Wallet
from leveller.tasks import register_sla_recipient_account
from tos.models import TOSConfig

logging.basicConfig(level=logging.INFO)


def register_token(token_address, name, short_name, register_on_chain):
    try:
        Token.objects.get(address=remove_0x_prefix(token_address))
        raise ValueError(
            'Token {} already registered in local db.'.format(token_address))
    except Token.DoesNotExist:
        pass

    if register_on_chain:
        NOCUSTContractInterface().register_ERC20(token_address)
        print('Registration transaction queued.')

    token = Token.objects.create(
        address=remove_0x_prefix(token_address),
        name=name,
        short_name=short_name,
        trail=Token.objects.count(),
        block=LocalViewInterface.latest_block())
    print('Token locally registered.')

    register_owner_account(token)

    if same_hex_value(token_address, settings.SLA_TOKEN_ADDRESS):
        register_sla_recipient_account()

    return token


def register_owner_account(token: Token):
    if Wallet.objects.filter(token=token, address=remove_0x_prefix(settings.HUB_OWNER_ACCOUNT_ADDRESS)).exists():
        return

    if not LocalViewInterface.get_contract_parameters():
        return

    latest_eon_number = LocalViewInterface.latest().eon_number()

    authorization_digest = Wallet(
        token=token, address=settings.HUB_OWNER_ACCOUNT_ADDRESS).get_admission_hash(latest_eon_number)
    authorization = sign_message(
        authorization_digest, settings.HUB_OWNER_ACCOUNT_KEY)
    latest_tos_config = TOSConfig.objects.all().order_by('time').last()
    tos_signature = sign_message(
        decode_hex(latest_tos_config.digest()), settings.HUB_OWNER_ACCOUNT_KEY)

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
