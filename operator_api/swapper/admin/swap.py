from django.db.models import Q

from ledger.models import Matching
from operator_api.locked_admin import ReadOnlyModelAdmin
from swapper.models import Swap


class SwapAdmin(ReadOnlyModelAdmin):
    list_display = [
        'eon_number',
        'wallet',
        'time',
        'amount',
        'price',
        'market',
        'processed',
        'complete',
        'cancelled',
        'matches',
    ]

    def price(self, obj: Swap):
        return '{:.2f}'.format(obj.amount / obj.amount_swapped)

    def market(self, obj: Swap):
        return '{}-{}'.format(obj.wallet.token.short_name, obj.recipient.token.short_name)

    def matches(self, obj: Swap):
        return Matching.objects.filter(Q(left_order_tx_id=obj.tx_id) | Q(right_order_tx_id=obj.tx_id)).count()

    def get_queryset(self, request):
        return super(SwapAdmin, self).get_queryset(request).filter(swap=True)
