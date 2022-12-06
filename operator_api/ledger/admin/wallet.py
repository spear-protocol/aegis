from operator_api.locked_admin import ReadOnlyModelAdmin


class WalletAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'address',
        'registration_eon_number',
        'registration_authorization',
    ]

    list_display = [
        'registration_eon_number',
        'address',
    ]
