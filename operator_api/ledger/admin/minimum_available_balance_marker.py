from operator_api.locked_admin import ReadOnlyModelAdmin


class MinimumAvailableBalanceMarkerAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'amount',
        'time',
        'eon_number',
        'signature'
    ]

    list_display = [
        'eon_number',
        'wallet',
        'amount',
        'time',
    ]
