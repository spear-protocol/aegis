from operator_api.crypto import hex_value
from operator_api.locked_admin import ReadOnlyModelAdmin
from ledger.models import ActiveState


class ActiveStateAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'wallet',
        'updated_spendings',
        'updated_gains',
        'wallet_signature',
        'operator_signature',
        'time',
        'eon_number',
        'tx_set_hash',
        'active_state_checksum'
    ]

    list_display = [
        'eon_number',
        'wallet',
        'updated_spendings',
        'updated_gains',
        'time',
    ]

    def active_state_checksum(self, obj: ActiveState):
        return hex_value(obj.checksum())
