import logging
from functools import cmp_to_key
from itertools import combinations
from django.conf import settings
from django.db import transaction, IntegrityError
from celery import shared_task
from celery.utils.log import get_task_logger
from contractor.interfaces import LocalViewInterface
from operator_api.decorators import notification_on_error
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import Transfer, RootCommitment, Token
from swapper.matcher import match_limit_to_limit, price_comparison_function
from swapper.util import should_void_swap, swap_expired
from django.core.cache import cache
from operator_api.celery import operator_celery
from sortedcontainers import SortedList
import datetime
from django.utils import timezone

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def process_swaps():

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    latest_eon_number = LocalViewInterface.latest().eon_number()

    # This lock is required because the ledger will be mutated as the swaps are processed
    with RootCommitment.global_lock():
        logger.info('Start')
        process_swaps_for_eon(latest_eon_number)


def process_swaps_for_eon(operator_eon_number):
    checkpoint_created = RootCommitment.objects.filter(
        eon_number=operator_eon_number).exists()

    notification_queue = []

    with transaction.atomic():
        default_time = timezone.now() - datetime.timedelta(days=365000)
        # Match swaps
        last_unprocessed_swap_time = timezone.make_aware(datetime.datetime.fromtimestamp(
            cache.get_or_set('last_unprocessed_swap_time', default_time.timestamp())))

        unprocessed_swaps = Transfer.objects \
            .filter(
                time__gte=last_unprocessed_swap_time,
                processed=False,
                complete=False,
                voided=False,
                cancelled=False,
                swap=True,
                eon_number=operator_eon_number,
                sender_active_state__operator_signature__isnull=False,
                recipient_active_state__operator_signature__isnull=False) \
            .select_for_update() \
            .order_by('time')

        order_books_cache = {}

        for swap in unprocessed_swaps:
            last_unprocessed_swap_time = max(
                last_unprocessed_swap_time, swap.time + datetime.timedelta(milliseconds=1))
            matched_successfully = False
            with transaction.atomic(), swap.lock(auto_renewal=True), swap.wallet.lock(auto_renewal=True), swap.recipient.lock(auto_renewal=True):
                swap_wallet_view_context = WalletTransferContext(
                    wallet=swap.wallet, transfer=swap)
                swap_recipient_view_context = WalletTransferContext(
                    wallet=swap.recipient, transfer=swap)

                if swap_expired(swap, operator_eon_number, checkpoint_created):
                    logger.info('Retiring swap')
                    swap.retire_swap()
                    continue
                if should_void_swap(swap, swap_wallet_view_context, swap_recipient_view_context, operator_eon_number, checkpoint_created):
                    logger.info('Voiding swap.')
                    swap.close(voided=True)
                    continue
                elif swap.is_fulfilled_swap():
                    logger.info('Skipping finalized swap.')
                    continue

                opposite_order_book_name = '{}-{}'.format(
                    swap.recipient.token.short_name, swap.wallet.token.short_name)

                # If this is a sell order then the opposite orderbook is for buys, which should be sorted
                # in decremental order by price such that the first element in the list is the highest priced
                opposite_comparison_function = price_comparison_function(
                    inverse=swap.sell_order, reverse=swap.sell_order)
                if opposite_order_book_name not in order_books_cache:
                    print("FETCHED")
                    opposite_swaps = Transfer.objects\
                        .filter(
                            id__lte=swap.id,
                            wallet__token=swap.recipient.token,
                            recipient__token=swap.wallet.token,
                            processed=False,
                            complete=False,
                            voided=False,
                            cancelled=False,
                            swap=True,
                            eon_number=operator_eon_number,
                            sender_active_state__operator_signature__isnull=False,
                            recipient_active_state__operator_signature__isnull=False)\
                        .select_for_update()

                    order_books_cache[opposite_order_book_name] = SortedList(
                        opposite_swaps, key=cmp_to_key(opposite_comparison_function))
                else:
                    print("CACHED")

                opposite_order_book = SortedList(
                    order_books_cache[opposite_order_book_name], key=cmp_to_key(opposite_comparison_function))
                opposite_orders_consumed = 0

                if len(opposite_order_book) == 0:
                    print("EMPTY")

                opposite_swaps = Transfer.objects \
                    .filter(
                        id__lte=swap.id,
                        wallet__token=swap.recipient.token,
                        recipient__token=swap.wallet.token,
                        processed=False,
                        complete=False,
                        voided=False,
                        cancelled=False,
                        swap=True,
                        eon_number=operator_eon_number,
                        sender_active_state__operator_signature__isnull=False,
                        recipient_active_state__operator_signature__isnull=False) \
                    .select_for_update()
                assert(len(opposite_order_book) == opposite_swaps.count())

                for opposite in opposite_order_book:
                    # BUY Price: amount / amount_swapped
                    # SELL Price: amount_swapped / amount

                    if swap.sell_order:
                        logger.info('SELL FOR {} VS BUY AT {}'.format(
                            swap.amount_swapped / swap.amount, opposite.amount / opposite.amount_swapped))

                    else:
                        logger.info('BUY AT {} VS SELL FOR {}'.format(
                            swap.amount / swap.amount_swapped, opposite.amount_swapped / opposite.amount))

                    # The invariant is that the buy order price is greater than or equal to the sell order price
                    invariant = swap.amount * \
                        opposite.amount >= opposite.amount_swapped * swap.amount_swapped

                    if not invariant:
                        break

                    with opposite.lock(auto_renewal=True), opposite.wallet.lock(auto_renewal=True), opposite.recipient.lock(auto_renewal=True):
                        opposite_wallet_view_context = WalletTransferContext(
                            wallet=opposite.wallet, transfer=opposite)
                        opposite_recipient_view_context = WalletTransferContext(
                            wallet=opposite.recipient, transfer=opposite)

                        if swap_expired(opposite, operator_eon_number, checkpoint_created):
                            opposite.retire_swap()
                            opposite_orders_consumed += 1
                            continue
                        if should_void_swap(opposite, opposite_wallet_view_context, opposite_recipient_view_context, operator_eon_number, checkpoint_created):
                            opposite.close(voided=True)
                            opposite_orders_consumed += 1
                            continue
                        elif opposite.is_fulfilled_swap():
                            opposite_orders_consumed += 1
                            continue

                        matched_successfully = match_limit_to_limit(
                            swap, opposite)

                        if opposite.is_fulfilled_swap():
                            opposite_orders_consumed += 1
                            try:
                                opposite.sign_swap_fulfillment(
                                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                                    settings.HUB_OWNER_ACCOUNT_KEY)
                            except LookupError as e:
                                logger.error(e)

                        if swap.is_fulfilled_swap():
                            try:
                                swap.sign_swap_fulfillment(
                                    settings.HUB_OWNER_ACCOUNT_ADDRESS,
                                    settings.HUB_OWNER_ACCOUNT_KEY)
                            except LookupError as e:
                                logger.error(e)

                        if swap.is_fulfilled_swap():
                            break

                order_books_cache[opposite_order_book_name] = opposite_order_book.islice(
                    opposite_orders_consumed)

                swap_order_book_name = '{}-{}'.format(
                    swap.wallet.token.short_name, swap.recipient.token.short_name)
                if not swap.is_fulfilled_swap() and swap_order_book_name in order_books_cache:
                    swap_comparison_function = price_comparison_function(
                        inverse=not swap.sell_order, reverse=not swap.sell_order)
                    swap_order_book = SortedList(
                        order_books_cache[swap_order_book_name], key=cmp_to_key(swap_comparison_function))
                    swap_order_book.add(swap)
                    order_books_cache[swap_order_book_name] = swap_order_book

            if matched_successfully:
                notification_queue.append((swap.id, opposite.id))

        cache.set('last_unprocessed_swap_time',
                  last_unprocessed_swap_time.timestamp())

    for swap_id, opposite_id in notification_queue:
        operator_celery.send_task(
            'auditor.tasks.on_swap_matching', args=[swap_id, opposite_id])
