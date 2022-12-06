import logging
from operator_api.decorators import notification_on_error
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db import transaction, IntegrityError

from contractor.interfaces import LocalViewInterface
from operator_api.crypto import hex_value
from ledger.models import Wallet, RootCommitment, Token
from ledger.models.blacklist import BlacklistEntry
from auditor.serializers import AdmissionSerializer
from synchronizer.utils import send_notification, REGISTERED_WALLET
from eth_utils import remove_0x_prefix

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def process_admissions():

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    # This lock is needed because new wallets can be introduced, which would affect the checkpoint.
    with RootCommitment.global_lock():
        process_admissions_for_latest_eon()


def should_void_admission(wallet, operator_eon_number, is_checkpoint_created):
    if wallet.registration_eon_number != operator_eon_number:
        if wallet.registration_eon_number == operator_eon_number - 1 and not is_checkpoint_created:
            pass
        else:
            logger.error('Wallet {} admission stale.'.format(wallet.address))
            return True

    if BlacklistEntry.objects.filter(address__iexact=wallet.address).exists():
        logger.error('Blacklisted address.')
        return True

    if wallet.registration_authorization.checksum != hex_value(wallet.get_admission_hash(operator_eon_number)):
        logger.error(
            'Invalid authorization checksum for {}.'.format(wallet.address))
        return True

    if not wallet.registration_authorization.is_valid():
        logger.error(
            'Invalid authorization signature for {}.'.format(wallet.address))
        return True

    return False


def process_admissions_for_latest_eon():
    latest_eon_number = LocalViewInterface.latest().eon_number()
    checkpoint_created = RootCommitment.objects.filter(
        eon_number=latest_eon_number).exists()

    to_update_records = []
    to_delete_ids = []
    wallet_offsets = {}
    operator_wallets = {}

    with transaction.atomic():
        pending_approval = Wallet.objects.select_for_update().filter(
            registration_operator_authorization__isnull=True)

        for token in Token.objects.all():
            wallet_offsets[token.id] = Wallet.objects.filter(
                registration_operator_authorization__isnull=False, token=token).count()

            try:
                operator_wallets[token.id] = Wallet.objects.get(
                    address=remove_0x_prefix(
                        settings.HUB_OWNER_ACCOUNT_ADDRESS),
                    token=token)
            except Wallet.DoesNotExist:
                logger.error('Could not admit client wallets for token {}. Owner wallet {} not yet registered.'.format(
                    token.address, settings.HUB_OWNER_ACCOUNT_ADDRESS))
                return

        for wallet in pending_approval:
            try:
                if wallet.registration_operator_authorization is not None:
                    logger.error(
                        'Wallet {} already admitted.'.format(wallet.address))
                    continue
                if should_void_admission(wallet, latest_eon_number, checkpoint_created):
                    to_delete_ids.append(wallet.id)
                    continue

                wallet.trail_identifier = wallet_offsets[wallet.token.id]

                wallet.registration_operator_authorization = wallet.sign_admission(
                    eon_number=latest_eon_number,
                    operator_wallet=operator_wallets[wallet.token.id],
                    private_key=settings.HUB_OWNER_ACCOUNT_KEY)

                wallet_offsets[wallet.token.id] += 1
                to_update_records.append(wallet)

            except IntegrityError as error:
                logger.error('Admission Verification Integrity Error')
                logger.error(error)
                break

        pending_approval.filter(pk__in=to_delete_ids).delete()

        Wallet.objects.bulk_update(
            to_update_records, ['registration_operator_authorization', 'trail_identifier'])

    for wallet in to_update_records:
        send_notification(
            stream_prefix="wallet",
            stream_id="{}/{}".format(wallet.token.address, wallet.address),
            event_name=REGISTERED_WALLET,
            data=AdmissionSerializer(
                wallet, read_only=True).data
        )
        logger.info('Wallet {} admitted.'.format(wallet.address))
