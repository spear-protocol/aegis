from django.core.validators import MinValueValidator
from django.db import models
from operator_api.models import CleanModel, MutexModel
from decimal import Decimal


class EthereumTransaction(CleanModel, MutexModel):
    chain_id = models.BigIntegerField()
    from_address = models.CharField(
        max_length=40)
    to_address = models.CharField(
        max_length=40)
    gas = models.BigIntegerField()
    data = models.TextField()
    value = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    nonce = models.BigIntegerField(unique=True)
    tag = models.CharField(
        max_length=512)
