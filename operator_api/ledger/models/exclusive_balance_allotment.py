from decimal import Decimal
from django.core.validators import MinValueValidator, validate_comma_separated_integer_list
from django.db import models
from eth_utils import remove_0x_prefix
from operator_api.crypto import encode_hex
from operator_api.models import CleanModel
from django.apps import apps


# Balance objects belong to the saved checkpoint merkle trees
class ExclusiveBalanceAllotment(CleanModel):
    wallet = models.ForeignKey(
        to='Wallet',
        on_delete=models.PROTECT)
    eon_number = models.BigIntegerField(
        db_index=True)
    left = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    right = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    merkle_proof_hashes = models.CharField(
        max_length=64*32,
        blank=True)
    merkle_proof_values = models.CharField(
        max_length=81*32,
        blank=True,
        validators=[validate_comma_separated_integer_list])
    merkle_proof_trail = models.DecimalField(
        max_digits=60,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    active_state = models.ForeignKey(
        to='ActiveState',
        on_delete=models.PROTECT,
        blank=True,
        null=True)

    class Meta:
        unique_together = [('wallet', 'eon_number')]

    def amount(self):
        return self.right - self.left

    def deltas(self):
        if self.active_state is None:
            return 0, 0
        return int(self.active_state.updated_spendings), int(self.active_state.updated_gains)

    def transaction_set_root(self):
        if self.active_state is None:
            return remove_0x_prefix(encode_hex(b'\0'*32))
        return self.active_state.tx_set_hash

    def active_state_checksum(self):
        if self.active_state is None:
            return b'\0'*32
        return self.active_state.checksum()

    def wallet_v_r_s(self):
        if self.active_state is None:
            return 0, 0, 0
        return self.active_state.wallet_signature.vrs()

    def operator_v_r_s(self):
        if self.active_state is None:
            return 0, 0, 0
        return self.active_state.operator_signature.vrs()

    def merkle_membership_chain(self):
        TokenCommitment = apps.get_model('ledger', 'TokenCommitment')
        try:
            commitment = TokenCommitment.objects.get(
                token=self.wallet.token, root_commitment__eon_number=self.eon_number)
        except TokenCommitment.DoesNotExist:
            return None
        return commitment.membership_hashes
