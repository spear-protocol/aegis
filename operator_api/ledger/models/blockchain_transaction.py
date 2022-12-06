from django.db import models
from .transaction import Transaction


# On-chain general transaction
class BlockchainTransaction(Transaction):
    txid = models.CharField(
        max_length=256)
    block = models.BigIntegerField(
        blank=True,
        null=True)

    class Meta:
        abstract = True


# On-chain deposit
class Deposit(BlockchainTransaction):
    pass


# On-chain withdrawal request
class WithdrawalRequest(BlockchainTransaction):
    slashed = models.BooleanField(default=False)

    def tag(self):
        return 'withdrawal_request_{}_{}_{}'.format(self.eon_number, self.wallet, self.amount)


# On-chain confirmed withdrawal
class Withdrawal(BlockchainTransaction):
    request = models.ForeignKey(
        to=WithdrawalRequest,
        on_delete=models.PROTECT)
