from django.contrib import admin

from contractor.admin.contract_ledger_state import ContractLedgerStateAdmin
from contractor.admin.contract_parameters import ContractParametersAdmin
from contractor.admin.contract_state import ContractStateAdmin
from contractor.models import (
    ContractParameters,
    ContractState,
    ContractLedgerState,
    EthereumTransaction)

# Register your models here.
admin.site.register(ContractParameters, ContractParametersAdmin)
admin.site.register(ContractState, ContractStateAdmin)
admin.site.register(ContractLedgerState, ContractLedgerStateAdmin)
admin.site.register(EthereumTransaction)
