from django.contrib import admin

from ledger.admin.active_state import ActiveStateAdmin
from ledger.admin.exclusive_balance_allotment import ExclusiveBalanceAllotmentAdmin
from ledger.admin.minimum_available_balance_marker import MinimumAvailableBalanceMarkerAdmin
from ledger.admin.checkpoint import CheckpointAdmin
from ledger.admin.deposit import DepositAdmin
from ledger.admin.signature import SignatureAdmin
from ledger.admin.transfer import TransferAdmin
from ledger.admin.wallet import WalletAdmin
from ledger.admin.withdrawal import WithdrawalAdmin
from ledger.admin.withdrawal_request import WithdrawalRequestAdmin
from ledger.models import (
    TokenCommitment,
    RootCommitment,
    ExclusiveBalanceAllotment,
    MinimumAvailableBalanceMarker,
    Wallet,
    ActiveState,
    Signature,
    Transfer,
    Deposit,
    WithdrawalRequest,
    Withdrawal,
    Token)

# Register your models here.
admin.site.register(ActiveState, ActiveStateAdmin)
admin.site.register(TokenCommitment, CheckpointAdmin)
admin.site.register(RootCommitment)
admin.site.register(ExclusiveBalanceAllotment, ExclusiveBalanceAllotmentAdmin)
admin.site.register(MinimumAvailableBalanceMarker,
                    MinimumAvailableBalanceMarkerAdmin)
admin.site.register(Deposit, DepositAdmin)
admin.site.register(Signature, SignatureAdmin)
admin.site.register(Token)
admin.site.register(Transfer, TransferAdmin)
admin.site.register(Wallet, WalletAdmin)
admin.site.register(WithdrawalRequest, WithdrawalRequestAdmin)
admin.site.register(Withdrawal, WithdrawalAdmin)
