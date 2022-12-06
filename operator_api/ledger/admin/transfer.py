from operator_api.locked_admin import ReadOnlyModelAdmin


class TransferAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'amount',
        'time',
        'eon_number',
        'sender_active_state',
        'recipient',
        'recipient_active_state',
        'nonce',
        'processed',
        'complete',
        'cancelled',
    ]

    list_display = [
        'eon_number',
        'time',
        'wallet',
        'recipient',
        'amount',
        'nonce',
        'processed',
        'complete',
        'cancelled',
    ]
