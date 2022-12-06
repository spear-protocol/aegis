from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from operator_api.models import CleanModel, MutexModel
from django.db import models


class Token(CleanModel, MutexModel):
    address = models.CharField(  # Case insensitive field
        max_length=40,
        unique=True,
        db_index=True)
    trail = models.IntegerField(
        unique=True,
        validators=[MinValueValidator(0)],
        db_index=True)

    name = models.CharField(
        max_length=40,
        blank=True,
        null=True)
    short_name = models.CharField(
        max_length=40,
        blank=True,
        null=True)

    block = models.BigIntegerField()

    def clean(self):
        if self.pk is None and Token.objects.filter(address__iexact=self.address).exists():
            raise ValidationError('Wallet already exists.')
