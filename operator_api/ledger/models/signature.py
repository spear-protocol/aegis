from django.core.exceptions import ValidationError
from django.db import models
from operator_api import crypto
from operator_api.models import CleanModel


# Signatures on messages by wallets
class Signature(CleanModel):
    wallet = models.ForeignKey(
        to='Wallet',
        null=True,
        on_delete=models.SET_NULL)
    checksum = models.CharField(
        max_length=64)
    value = models.CharField(
        max_length=130)
    data = models.CharField(
        max_length=4096,
        blank=True,
        null=True)

    # The text representation is wallet, checksum
    def __str__(self):
        return self.value

    # Return the v, r, s values of a signature
    def vrs(self):
        return crypto.decode_signature(self.value)

    # Check if the signature matches the checksum
    def is_valid(self):
        return crypto.verify_message_signature(crypto.address(self.wallet.address),
                                               crypto.decode_hex(
                                                   self.checksum),
                                               self.vrs())

    # Only save valid signatures
    def clean(self):
        if not self.is_valid():
            raise ValidationError('Could not validate signature.')
