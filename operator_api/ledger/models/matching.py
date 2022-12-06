from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Matching(models.Model):
    # Left/Right hand side
    left_order_tx_id = models.UUIDField(blank=True, null=True, db_index=True)
    right_order_tx_id = models.UUIDField(blank=True, null=True, db_index=True)
    # Outgoing (incoming) amounts
    left_deducted_right_granted_amount = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    right_deducted_left_granted_amount = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    # Timestamp
    creation_time = models.DateTimeField(
        auto_now_add=True)
    # Eon matched
    eon_number = models.BigIntegerField(blank=True, null=True, db_index=True)
    left_token = models.ForeignKey(
        to='Token',
        on_delete=models.PROTECT,
        related_name="left_token",
        blank=True, null=True)
    right_token = models.ForeignKey(
        to='Token',
        on_delete=models.PROTECT,
        related_name="right_token",
        blank=True, null=True)

    def get_timestamp(self):
        return int(self.creation_time.timestamp())
