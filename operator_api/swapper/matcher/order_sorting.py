from ledger.models import Transfer


def price_comparison_function(inverse=False, reverse=False):
    def compare_orders_by_price(left_order: Transfer, right_order: Transfer):
        assert (left_order.wallet.token == right_order.wallet.token)
        assert (left_order.recipient.token == right_order.recipient.token)

        if not inverse:
            # left_order.amount_swapped / left_order.amount > right_order.amount_swapped / right_order.amount
            lhs = left_order.amount_swapped * right_order.amount
            rhs = right_order.amount_swapped * left_order.amount
        else:  # use 1/price
            # left_order.amount / left_order.amount_swapped > right_order.amount / right_order.amount_swapped
            lhs = left_order.amount * right_order.amount_swapped
            rhs = right_order.amount * left_order.amount_swapped

        if not reverse:
            return lhs - rhs
        else:
            return rhs - lhs

    return compare_orders_by_price
