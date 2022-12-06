from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models

from operator_api import crypto
from operator_api.models import CleanModel, MutexModel


class TokenCommitment(CleanModel, MutexModel):
    token = models.ForeignKey(
        to='Token',
        on_delete=models.PROTECT)
    merkle_root = models.CharField(
        max_length=64)
    upper_bound = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    root_commitment = models.ForeignKey(
        to='RootCommitment',
        on_delete=models.PROTECT,
        blank=True,
        null=True)
    membership_hashes = models.CharField(
        max_length=64 * 32,
        blank=True,
        null=True)

    def __str__(self):
        return '%s %s %s %s' % (self.root_commitment.eon_number, self.token.address, self.merkle_root, self.upper_bound)

    def tag(self):
        return 'token_checkpoint_{}_{}_{}_{}'.format(self.root_commitment.eon_number, self.token.address, self.merkle_root, self.upper_bound)

    def shorthand(self):
        return {
            'left': 0,
            'merkle_root': self.merkle_root,
            'right': int(self.upper_bound),
            'hash': self.checksum()
        }

    def checksum(self):
        representation = [
            crypto.uint256(0),
            crypto.decode_hex(self.merkle_root),
            crypto.uint256(int(self.upper_bound))
        ]
        return crypto.hash_array(representation)
