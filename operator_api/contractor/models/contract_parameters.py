from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from operator_api.models import CleanModel, MutexModel


class ContractParameters(CleanModel, MutexModel):
    genesis_block = models.BigIntegerField()
    blocks_per_eon = models.BigIntegerField()
    eons_kept = models.BigIntegerField()
    challenge_cost = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
