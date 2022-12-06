from functools import cmp_to_key

from rest_framework import serializers
from auditor.util import SwapDataRequest
from ledger.models import Transfer
from swapper.matcher import price_comparison_function
from .order import OrderSerializer
from contractor.interfaces import LocalViewInterface


class OrderBookSerializer(serializers.Serializer):
    sell_orders = OrderSerializer(many=True, read_only=True)
    buy_orders = OrderSerializer(many=True, read_only=True)

    def to_representation(self, swap_data_request: SwapDataRequest):
        latest = LocalViewInterface.latest().eon_number()
        eon_number = swap_data_request.eon_number if 0 <= swap_data_request.eon_number <= latest else latest
        all_sell_orders = Transfer.objects.filter(
            wallet__token=swap_data_request.left_token,
            recipient__token=swap_data_request.right_token,
            processed=False,
            complete=False,
            voided=False,
            cancelled=False,
            swap=True,
            eon_number=eon_number)

        all_sell_orders = sorted(all_sell_orders, key=cmp_to_key(
            price_comparison_function(inverse=True)))

        all_buy_orders = Transfer.objects.filter(
            wallet__token=swap_data_request.right_token,
            recipient__token=swap_data_request.left_token,
            processed=False,
            complete=False,
            voided=False,
            cancelled=False,
            swap=True,
            eon_number=eon_number)

        all_buy_orders = sorted(all_buy_orders, key=cmp_to_key(
            price_comparison_function(inverse=False)))

        return {
            'sell_orders': OrderSerializer(combine_order_volumes(all_sell_orders), many=True, read_only=True).data,
            'buy_orders': OrderSerializer(combine_order_volumes(all_buy_orders), many=True, read_only=True).data,
        }


def combine_order_volumes(orders: [Transfer]):
    combined_orders = []

    for order in orders:
        matched_out, matched_in = order.matched_amounts(all_eons=True)
        if order.sell_order:
            remaining_out = order.amount - matched_out
            remaining_in = int(
                remaining_out * order.amount_swapped) // int(order.amount)
        else:
            remaining_in = order.amount_swapped - matched_in
            remaining_out = int(
                remaining_in * order.amount) // int(order.amount_swapped)

        i = len(combined_orders) - 1
        if i < 0 or combined_orders[i].get('amount') * order.amount_swapped != combined_orders[i].get('amount_swapped') * order.amount:
            combined_orders.append({
                'amount': int(order.amount),
                'amount_swapped': int(order.amount_swapped),
                'remaining_out': int(remaining_out),
                'remaining_in': int(remaining_in),
            })
        else:
            combined_orders[i].update({
                'remaining_out': combined_orders[i].get('remaining_out') + remaining_out,
                'remaining_in': combined_orders[i].get('remaining_in') + remaining_in,
            })

    return combined_orders
