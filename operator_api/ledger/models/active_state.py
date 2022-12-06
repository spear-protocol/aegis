from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

from operator_api.crypto import sign_message, hex_value, encode_signature
from operator_api.models import CleanModel
from django.core.exceptions import ValidationError
from operator_api import crypto
from eth_utils import keccak, remove_0x_prefix
from operator_api.util import long_string_to_list


# Active State Updates
class ActiveState(CleanModel):
    wallet = models.ForeignKey(
        to='Wallet',
        on_delete=models.PROTECT)
    updated_spendings = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    updated_gains = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))],
        blank=True,
        null=True)
    wallet_signature = models.ForeignKey(
        to='Signature',
        on_delete=models.PROTECT,
        related_name='active_state_wallet_signature')
    operator_signature = models.ForeignKey(
        to='Signature',
        on_delete=models.PROTECT,
        related_name='active_state_operator_signature',
        blank=True,
        null=True)
    time = models.DateTimeField(
        auto_now_add=True)
    eon_number = models.BigIntegerField(
        db_index=True)
    tx_set_hash = models.CharField(
        max_length=64)
    tx_set_proof_hashes = models.CharField(
        max_length=64 * 32,
        blank=True)
    tx_set_index = models.BigIntegerField()

    def get_timestamp(self):
        return int(self.time.timestamp())

    def checksum(self):
        representation = [
            keccak(crypto.address(settings.HUB_LQD_CONTRACT_ADDRESS)),
            keccak(crypto.address(self.wallet.token.address)),
            keccak(crypto.address(self.wallet.address)),
            crypto.uint64(
                self.wallet.trail_identifier if self.wallet.trail_identifier is not None else 0),
            crypto.uint256(self.eon_number),
            crypto.decode_hex(self.tx_set_hash),
            crypto.uint256(self.updated_spendings),
            crypto.uint256(self.updated_gains)
        ]

        return crypto.hash_array(representation)

    def clean(self):
        if not self.wallet_signature.is_valid():
            raise ValidationError("Incorrect sender signature.")
        elif self.wallet_signature.checksum != crypto.hex_value(self.checksum()):
            raise ValidationError("Invalid sender active state checksum.")

        if self.operator_signature is not None:
            if not self.operator_signature.is_valid():
                raise ValidationError("Incorrect sender signature.")
            elif self.operator_signature.checksum != self.wallet_signature.checksum:
                raise ValidationError(
                    "Invalid operator active state checksum.")

    def tx_set_proof_hashes_formatted(self):
        return long_string_to_list(self.tx_set_proof_hashes, 64)

    def sign_active_state(self, address, private_key):
        raw_checksum = self.checksum()
        vrs = sign_message(
            m=raw_checksum,
            k=private_key)

        Wallet = apps.get_model('ledger', 'Wallet')
        try:
            operator_wallet = Wallet.objects.get(
                token=self.wallet.token,
                address=remove_0x_prefix(address))
        except Wallet.DoesNotExist:
            raise LookupError(
                'Signing wallet {} is not yet registered'.format(address))

        Signature = apps.get_model('ledger', 'Signature')
        operator_signature = Signature.objects.create(
            wallet=operator_wallet,
            checksum=hex_value(raw_checksum),
            value=encode_signature(vrs))

        return operator_signature
