from operator_api.locked_admin import ReadOnlyModelAdmin


class SignatureAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'checksum',
        'value',
        'data'
    ]

    list_display = [
        'wallet',
        'checksum'
    ]
