from operator_api.locked_admin import ReadOnlyModelAdmin


class CheckpointAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'token',
        'merkle_root',
        'upper_bound'
    ]

    list_display = [
        'token',
        'merkle_root',
        'upper_bound'
    ]
