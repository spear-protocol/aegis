from django.db import models
from operator_api.models import CleanModel, MutexModel


class Agreement(CleanModel, MutexModel):
    wallet = models.ForeignKey(
        to='ledger.Wallet',
        on_delete=models.PROTECT)

    transfer = models.ForeignKey(
        to='ledger.Transfer',
        on_delete=models.PROTECT,
        blank=True,
        null=True)

    beginning = models.DateTimeField(
        auto_now_add=True)

    expiry = models.DateTimeField()

    def get_timestamp(self):
        return int(self.expiry.timestamp())
