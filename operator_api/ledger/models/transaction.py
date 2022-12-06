from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from operator_api.models import CleanModel, MutexModel
from django.utils import timezone


# Shared transaction fields
class Transaction(CleanModel, MutexModel):
    wallet = models.ForeignKey(
        to='Wallet',
        on_delete=models.PROTECT)
    amount = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    time = models.DateTimeField(
        default=timezone.now, editable=False, db_index=True)
    eon_number = models.BigIntegerField(
        db_index=True)

    class Meta:
        abstract = True

    def get_timestamp(self):
        return int(self.time.timestamp())
