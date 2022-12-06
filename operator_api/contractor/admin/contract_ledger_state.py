from operator_api.locked_admin import ReadOnlyModelAdmin


class ContractLedgerStateAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'contract_state',
        'token',
        'pending_withdrawals',
        'confirmed_withdrawals',
        'deposits',
        'total_balance'
    ]

    list_display = [
        'block',
        'short_name',
        'pending_withdrawals',
        'confirmed_withdrawals',
        'deposits',
        'total_balance'
    ]

    def block(self, obj):
        return obj.contract_state.block

    def short_name(self, obj):
        return obj.token.short_name
