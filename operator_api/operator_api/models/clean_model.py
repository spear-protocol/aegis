from django.db import models


# Basis
class CleanModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super(CleanModel, self).save(*args, **kwargs)

    def save_dirty(self, *args, **kwargs):
        return super(CleanModel, self).save(*args, **kwargs)
