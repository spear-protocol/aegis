from django.db import models
from operator_api.models import CleanModel, MutexModel
from django.utils import timezone
from operator_api.crypto import decode_hex, hash_array, encode_hex, remove_0x_prefix


class TOSConfig(CleanModel, MutexModel):
    privacy_policy_digest = models.CharField(
        max_length=64, null=False, blank=False)
    terms_of_service_digest = models.CharField(
        max_length=64, null=False, blank=False)
    time = models.DateTimeField(
        default=timezone.now, editable=False, db_index=True)

    class Meta:
        unique_together = (
            ('privacy_policy_digest', 'terms_of_service_digest'),)

    def digest(self):
        return remove_0x_prefix(encode_hex(hash_array([
            decode_hex(self.terms_of_service_digest),
            decode_hex(self.privacy_policy_digest)])))

    def get_timestamp(self):
        return int(self.time.timestamp())


class TOSSignature(CleanModel, MutexModel):
    address = models.CharField(
        max_length=40,
        db_index=True)
    tos_config = models.ForeignKey(
        to='TOSConfig',
        on_delete=models.PROTECT,
        blank=True,
        null=True)
    tos_signature = models.ForeignKey(
        to='ledger.Signature',
        on_delete=models.PROTECT,
        blank=True,
        null=True)

    class Meta:
        unique_together = (('address', 'tos_config'),)
