from django.core.validators import MinValueValidator
from django.db import models
from operator_api.models import CleanModel, MutexModel
from decimal import Decimal


class EthereumTransactionAttempt(CleanModel, MutexModel):
    transaction = models.ForeignKey(
        to='EthereumTransaction',
        on_delete=models.PROTECT)
    block = models.BigIntegerField()
    gas_price = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    signed_attempt = models.TextField()
    hash = models.CharField(
        max_length=64,
        unique=True)
    mined = models.BigIntegerField(
        blank=True,
        null=True)
    confirmed = models.BooleanField(
        default=False)
