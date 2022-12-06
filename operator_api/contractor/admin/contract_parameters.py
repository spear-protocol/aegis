from operator_api.locked_admin import ReadOnlyModelAdmin


class ContractParametersAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'genesis_block',
        'blocks_per_eon',
        'challenge_cost'
    ]

    list_display = [
        'genesis_block',
        'blocks_per_eon',
        'challenge_cost'
    ]
