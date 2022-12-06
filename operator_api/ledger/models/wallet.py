from datetime import datetime, timezone

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Max, Q
from eth_utils import remove_0x_prefix

from operator_api.crypto import hex_value, sign_message, encode_signature, same_hex_value
from operator_api.models import CleanModel, MutexModel
from django.apps import apps


class Wallet(CleanModel, MutexModel):
    address = models.CharField(  # Case insensitive field
        max_length=40,
        db_index=True)
    token = models.ForeignKey(
        to='Token',
        on_delete=models.PROTECT)
    registration_eon_number = models.BigIntegerField(
        validators=[MinValueValidator(0)],
        db_index=True)
    registration_authorization = models.ForeignKey(
        to='Signature',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='wallet_registration_signature')
    registration_operator_authorization = models.ForeignKey(
        to='Signature',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='operator_registration_signature')
    trail_identifier = models.BigIntegerField(
        blank=True,
        null=True,
        db_index=True)

    class Meta:
        unique_together = [
            ('token', 'address'),
            ('token', 'trail_identifier'),
        ]

    def clean(self):
        if self.pk is None and Wallet.objects.filter(
                address__iexact=self.address,
                token__address__iexact=self.token.address)\
                .exists():
            raise ValidationError('Wallet already exists.')

    def get_admission_hash(self, eon_number):
        ActiveState = apps.get_model('ledger', 'ActiveState')

        zero_state = ActiveState(
            wallet=self,
            updated_spendings=0,
            updated_gains=0,
            eon_number=eon_number,
            tx_set_hash='0000000000000000000000000000000000000000000000000000000000000000')

        return zero_state.checksum()

    def is_admitted(self):
        return self.registration_operator_authorization is not None and self.trail_identifier is not None

    def sign_admission(self, eon_number, operator_wallet, private_key):
        admission_hash = self.get_admission_hash(eon_number)
        admission_hash_encoded = hex_value(admission_hash)

        vrs = sign_message(
            m=admission_hash,
            k=private_key)

        Signature = apps.get_model('ledger', 'Signature')
        operator_signature = Signature.objects.create(
            wallet=operator_wallet,
            checksum=admission_hash_encoded,
            value=encode_signature(vrs))

        return operator_signature

    def has_valid_sla(self):
        Agreement = apps.get_model('leveller', 'Agreement')

        now = datetime.now(tz=timezone.utc)

        return Agreement.objects.filter(
            wallet__address__iexact=remove_0x_prefix(self.address),
            expiry__gte=now)\
            .exists()

    def is_sla_exempt(self):
        return same_hex_value(self.address, settings.HUB_OWNER_ACCOUNT_ADDRESS)\
            or same_hex_value(self.address, settings.SLA_RECIPIENT_ADDRESS)

    # Text representation of a wallet is its address
    def __str__(self):
        return '0x' + self.address
