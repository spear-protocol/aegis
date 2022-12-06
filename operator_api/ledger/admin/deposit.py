from operator_api.locked_admin import ReadOnlyModelAdmin


class DepositAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'amount',
        'time',
        'eon_number',
        'txid',
        'block'
    ]

    list_display = [
        'block',
        'txid',
        'wallet',
        'amount',
        'time'
    ]
