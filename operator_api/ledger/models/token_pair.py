from django.db import models
from operator_api import crypto


class TokenPair(models.Model):
    token_from = models.ForeignKey(
        to='Token',
        related_name='from_pairs',
        on_delete=models.CASCADE)

    token_to = models.ForeignKey(
        to='Token',
        related_name='to_pairs',
        on_delete=models.CASCADE)

    conduit = models.CharField(
        max_length=40,
        blank=True,
        unique=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            result = crypto.hash_array(
                [crypto.address(self.token_from.address), crypto.address(self.token_to.address)])
            self.conduit = crypto.hex_address(crypto.hex_value(result))
        super(TokenPair, self).save(*args, **kwargs)
