from django.db import models


# This is an admission blacklist entry barring a wallet address from registration because it may have made a deposit
# before being allowed admission.
class BlacklistEntry(models.Model):
    address = models.CharField(  # Case insensitive field
        max_length=40,
        unique=True)
