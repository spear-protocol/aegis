from django.db import models
from operator_api.models import CleanModel, MutexModel


class RootCommitment(CleanModel, MutexModel):
    eon_number = models.BigIntegerField(
        db_index=True)
    basis = models.CharField(
        max_length=64)
    merkle_root = models.CharField(
        max_length=64)
    block = models.BigIntegerField()

    class Meta:
        unique_together = [
            ('eon_number', 'basis')
        ]

    def tag(self):
        return 'root_checkpoint_{}_{}_{}'.format(self.eon_number, self.basis, self.merkle_root)
