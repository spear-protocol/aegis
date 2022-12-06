import logging
from django.conf import settings
from django.db import transaction
from celery import shared_task
from celery.utils.log import get_task_logger
from contractor.interfaces import LocalViewInterface
from ledger.models import Transfer, RootCommitment
from operator_api.decorators import notification_on_error

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def cancel_finalize_swaps():

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    latest_eon_number = LocalViewInterface.latest().eon_number()

    # This lock is required because the ledger will be mutated as the swaps are processed
    with RootCommitment.global_lock():
        cancel_finalize_swaps_for_eon(latest_eon_number)


def cancel_finalize_swaps_for_eon(operator_eon_number):
    with transaction.atomic():
        # Countersign finalizations (full matching + extra credit)
        swaps_pending_operator_finalization = Transfer.objects \
            .filter(
                swap=True,
                processed=False,
                complete=True,
                voided=False,
                cancelled=False,
                recipient_finalization_active_state__isnull=False) \
            .select_for_update() \
            .order_by('time')

        for swap in swaps_pending_operator_finalization:
            with transaction.atomic():
                swap.sign_swap_finalization(
                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                    settings.HUB_OWNER_ACCOUNT_KEY)
                swap.close(complete=True, appended=True)


        # Countersign cancellations (partial matching)
        swaps_pending_operator_cancellation = Transfer.objects \
            .filter(
                swap=True,
                processed=False,
                complete=False,
                voided=False,
                cancelled=True,
                sender_cancellation_active_state__isnull=False,
                recipient_cancellation_active_state__isnull=False) \
            .select_for_update() \
            .order_by('time')

        for swap in swaps_pending_operator_cancellation:
            with transaction.atomic():
                if not swap.is_signed_by_operator():
                    swap.cancelled = False
                    swap.sign_swap(
                        settings.HUB_OWNER_ACCOUNT_ADDRESS,
                        settings.HUB_OWNER_ACCOUNT_KEY)
                    swap.cancelled = True
                swap.sign_swap_cancellation(
                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                    settings.HUB_OWNER_ACCOUNT_KEY)
                swap.close(cancelled=True, appended=True)

