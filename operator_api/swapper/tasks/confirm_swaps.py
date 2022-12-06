import logging
from django.conf import settings
from django.db import transaction
from celery import shared_task
from celery.utils.log import get_task_logger
from contractor.interfaces import LocalViewInterface
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Transfer, RootCommitment
from swapper.util import swap_expired, should_void_swap
from operator_api.celery import operator_celery
from operator_api.decorators import notification_on_error
logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def confirm_swaps():

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    latest_eon_number = LocalViewInterface.latest().eon_number()

    # This lock is required because the ledger will be mutated as the swaps are processed
    with RootCommitment.global_lock():
        confirm_swaps_for_eon(latest_eon_number)


def confirm_swaps_for_eon(operator_eon_number):
    checkpoint_created = RootCommitment.objects.filter(
        eon_number=operator_eon_number).exists()
    with transaction.atomic():
        # Countersign swaps (no matching yet)
        swaps_pending_operator_confirmation = Transfer.objects \
            .filter(
                processed=False,
                complete=False,
                voided=False,
                cancelled=False,
                swap=True,
                eon_number=operator_eon_number,
                sender_active_state__isnull=False,
                recipient_active_state__isnull=False,
                sender_active_state__operator_signature__isnull=True,
                recipient_active_state__operator_signature__isnull=True) \
            .select_for_update() \
            .order_by('time')

        for swap in swaps_pending_operator_confirmation:
            with swap.lock(auto_renewal=True), swap.wallet.lock(auto_renewal=True), swap.recipient.lock(auto_renewal=True):
                swap_wallet_view_context = WalletTransferContext(
                    wallet=swap.wallet, transfer=swap)
                swap_recipient_view_context = WalletTransferContext(
                    wallet=swap.recipient, transfer=swap)

                if swap_expired(swap, operator_eon_number, checkpoint_created):
                    logger.info('Retiring swap')
                    swap.retire_swap()
                if should_void_swap(swap, swap_wallet_view_context, swap_recipient_view_context, operator_eon_number, checkpoint_created):
                    logger.info('Voiding swap.')
                    swap.close(voided=True)
                elif swap.is_fulfilled_swap():
                    logger.info('Skipping finalized swap.')
                elif swap.is_signed_by_operator():
                    logger.info('Skipping signed swap.')
                else:
                    try:
                        swap.sign_swap(
                            settings.HUB_OWNER_ACCOUNT_ADDRESS,
                            settings.HUB_OWNER_ACCOUNT_KEY)

                        operator_celery.send_task(
                            'auditor.tasks.on_swap_confirmation', args=[swap.id])
                    except LookupError as e:
                        logger.error(e)
