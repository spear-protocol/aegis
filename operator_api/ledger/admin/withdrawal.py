from operator_api.locked_admin import ReadOnlyModelAdmin


class WithdrawalAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'amount',
        'time',
        'eon_number',
        'txid',
        'block',
        'request'
    ]

    list_display = [
        'block',
        'txid',
        'wallet',
        'amount',
        'time'
    ]
