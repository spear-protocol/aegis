from operator_api.locked_admin import ReadOnlyModelAdmin


class ExclusiveBalanceAllotmentAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'eon_number',
        'left',
        'right',
        'merkle_proof_hashes',
        'merkle_proof_values',
        'merkle_proof_trail',
        'active_state'
    ]

    list_display = [
        'eon_number',
        'wallet',
        'amount',
    ]
