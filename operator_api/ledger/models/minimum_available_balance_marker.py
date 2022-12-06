from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from operator_api import crypto
from operator_api.models import CleanModel
from eth_utils import keccak


class MinimumAvailableBalanceMarker(CleanModel):
    wallet = models.ForeignKey(
        to='Wallet',
        on_delete=models.PROTECT)
    amount = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    time = models.DateTimeField(
        auto_now_add=True)
    eon_number = models.BigIntegerField(
        db_index=True)
    signature = models.ForeignKey(
        to='Signature',
        on_delete=models.PROTECT,
        blank=True,
        null=True)

    def get_timestamp(self):
        return int(self.time.timestamp())

    def checksum(self):
        representation = [
            keccak(crypto.address(settings.HUB_LQD_CONTRACT_ADDRESS)),
            keccak(crypto.address(self.wallet.token.address)),
            keccak(crypto.address(self.wallet.address)),
            crypto.uint256(self.eon_number),
            crypto.uint256(self.amount)
        ]
        return crypto.hash_array(representation)

    def clean(self):
        if not self.signature.is_valid():
            raise ValidationError("Incorrect sender signature on balance.")
        elif self.signature.checksum != crypto.hex_value(self.checksum()):
            raise ValidationError("Invalid sender balance checksum.")
