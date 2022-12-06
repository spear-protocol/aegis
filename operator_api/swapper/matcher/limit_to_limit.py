from ledger.models import Transfer, Matching
import logging
from celery.utils.log import get_task_logger
from django.db import transaction, IntegrityError


logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


# The price of the right order is to be taken in this context, which means that the left order should be the more recent
# order to align with the pricing strategy
# returns true if orders were matched
def match_limit_to_limit(left_order: Transfer, right_order: Transfer):
    assert(left_order.wallet.token == right_order.recipient.token)
    assert(left_order.recipient.token == right_order.wallet.token)

    assert (left_order.amount_swapped * right_order.amount_swapped <=
            right_order.amount * left_order.amount)

    # fetch all past matches
    left_matched_out, left_matched_in = left_order.matched_amounts(
        all_eons=True)
    right_matched_out, right_matched_in = right_order.matched_amounts(
        all_eons=True)

    left_remaining_out = left_order.amount - left_matched_out
    left_remaining_in = left_order.amount_swapped - left_matched_in
    right_remaining_out = right_order.amount - right_matched_out
    right_remaining_in = right_order.amount_swapped - right_matched_in

    if left_order.sell_order:
        max_left_order_incoming_token_volume = int(
            left_remaining_out * right_order.amount) // right_order.amount_swapped
        max_left_order_outgoing_token_volume = left_remaining_out
    else:
        max_left_order_incoming_token_volume = left_remaining_in
        max_left_order_outgoing_token_volume = int(
            left_remaining_in * right_order.amount_swapped) // right_order.amount

    if right_order.sell_order:
        max_right_order_incoming_token_volume = int(
            right_remaining_out * right_order.amount_swapped) // right_order.amount
        max_right_order_outgoing_token_volume = right_remaining_out
    else:
        max_right_order_incoming_token_volume = right_remaining_in
        max_right_order_outgoing_token_volume = int(
            right_remaining_in * right_order.amount) // right_order.amount_swapped

    left_to_right_token_volume_traded = max_left_order_outgoing_token_volume
    right_to_left_token_volume_traded = max_left_order_incoming_token_volume

    # If the left order can give more than the right can take, or takes more than the right can give
    if left_to_right_token_volume_traded > max_right_order_incoming_token_volume or right_to_left_token_volume_traded > max_right_order_outgoing_token_volume:
        # Downsize the volume to the maximum that can be offered by the right order
        left_to_right_token_volume_traded = max_right_order_incoming_token_volume
        right_to_left_token_volume_traded = max_right_order_outgoing_token_volume

    logger.info('max_left_order_incoming_token_volume: {}'.format(
        max_left_order_incoming_token_volume))
    logger.info('max_left_order_outgoing_token_volume: {}'.format(
        max_left_order_outgoing_token_volume))
    logger.info('max_right_order_incoming_token_volume: {}'.format(
        max_right_order_incoming_token_volume))
    logger.info('max_right_order_outgoing_token_volume: {}'.format(
        max_right_order_outgoing_token_volume))
    logger.info('left_to_right_token_volume_traded: {}'.format(
        left_to_right_token_volume_traded))
    logger.info('right_to_left_token_volume_traded: {}'.format(
        right_to_left_token_volume_traded))

    # Calculate the new values after enacting the traded volumes
    new_left_matched_out = left_matched_out + left_to_right_token_volume_traded
    new_left_matched_in = left_matched_in + right_to_left_token_volume_traded
    new_right_matched_out = right_matched_out + right_to_left_token_volume_traded
    new_right_matched_in = right_matched_in + left_to_right_token_volume_traded

    # if this matching is at a price fractionally lower than what the seller is selling for
    # if new_left_matched_in / new_left_matched_out < left_order.amount_swapped / left_order.amount:
    if int(new_left_matched_in * left_order.amount) // 100 < int(left_order.amount_swapped * new_left_matched_out) // 100:
        logger.error(
            'Matching tips price fractionally lower than seller limit price.')
        logger.error((new_left_matched_in, new_left_matched_out,))
        logger.error((left_order.amount_swapped, left_order.amount,))
        return False

    # if this matching is at a price fractionally higher than what the buyer is buying for
    # if new_right_matched_in / new_right_matched_out < right_order.amount_swapped / right_order.amount:
    if int(new_right_matched_in * right_order.amount) // 100 < int(right_order.amount_swapped * new_right_matched_out) // 100:
        logger.error(
            'Matching tips price fractionally higher than buyer limit price.')
        logger.error((new_right_matched_in, new_right_matched_out,))
        logger.error((right_order.amount_swapped, right_order.amount,))
        return False

    if new_left_matched_out > left_order.amount:
        logger.error('Matching overspends seller limit.')
        return False

    if new_right_matched_out > right_order.amount:
        logger.error('Matching overspends buyer limit.')
        return False

    try:
        with transaction.atomic():
            Matching.objects.create(
                eon_number=left_order.eon_number,
                left_order_tx_id=left_order.tx_id,
                right_order_tx_id=right_order.tx_id,
                left_deducted_right_granted_amount=left_to_right_token_volume_traded,
                right_deducted_left_granted_amount=right_to_left_token_volume_traded,
                left_token=left_order.wallet.token,
                right_token=right_order.wallet.token)
            logger.info('Match {}-{}: {}/{}'.format(
                left_order.tx_id,
                right_order.tx_id,
                left_to_right_token_volume_traded,
                right_to_left_token_volume_traded))

            if new_left_matched_out == left_order.amount:
                assert(new_left_matched_in >= left_order.amount_swapped)
                logger.info('L-Order {} complete. (+{})'.format(left_order.id,
                                                                new_left_matched_in - left_order.amount_swapped))
                logger.info('L-Sell-Order {} complete. (+{})'.format(left_order.id,
                                                                     new_left_matched_in - left_order.amount_swapped))
                left_order.change_state(complete=True, appended=True)
            elif (not left_order.sell_order) and new_left_matched_in == left_order.amount_swapped:
                assert(new_left_matched_out <= left_order.amount)
                logger.info('L-Buy-Order {} complete. (+{})'.format(left_order.id,
                                                                    left_order.amount - new_left_matched_out))
                left_order.change_state(complete=True, appended=True)
            elif not left_order.sell_order:
                assert(new_left_matched_in < left_order.amount_swapped)

            if new_right_matched_out == right_order.amount:
                assert(new_right_matched_in >= right_order.amount_swapped)
                logger.info('R-Order {} complete. (+{})'.format(right_order.id,
                                                                new_right_matched_in - right_order.amount_swapped))
                logger.info('R-Sell-Order {} complete. (+{})'.format(right_order.id,
                                                                     new_right_matched_in - right_order.amount_swapped))
                right_order.change_state(complete=True, appended=True)
            elif (not right_order.sell_order) and new_right_matched_in == right_order.amount_swapped:
                assert(new_right_matched_out <= right_order.amount)
                logger.info('R-Buy-Order {} complete. (+{})'.format(right_order.id,
                                                                    right_order.amount - new_right_matched_out))
                right_order.change_state(complete=True, appended=True)
            elif not right_order.sell_order:
                assert(new_right_matched_in < right_order.amount_swapped)
    except IntegrityError:
        return False

    return True
