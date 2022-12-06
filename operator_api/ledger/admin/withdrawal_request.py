from operator_api.locked_admin import ReadOnlyModelAdmin


class WithdrawalRequestAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'amount',
        'time',
        'eon_number',
        'txid',
        'block',
        'slashed'
    ]

    list_display = [
        'block',
        'txid',
        'wallet',
        'amount',
        'slashed',
        'time'
    ]
