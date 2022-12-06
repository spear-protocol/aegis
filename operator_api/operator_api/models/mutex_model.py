from django.conf import settings
from django.db import models
import redis
import redis_lock
from .locks import ReadWriteLock


strict_redis_client = redis.StrictRedis(
    host=settings.CACHE_REDIS_HOST,
    port=settings.CACHE_REDIS_PORT,
    db=0)


class MutexModel(models.Model):
    class Meta:
        abstract = True,

    def lock(self, acquirer_id=None, auto_renewal=False, expiry_seconds=5):
        return redis_lock.Lock(
            redis_client=strict_redis_client,
            name='{0}__locked:{1}'.format(self.__class__.__name__, self.id),
            expire=expiry_seconds,
            id=acquirer_id,
            auto_renewal=auto_renewal,
            strict=True)

    @classmethod
    def global_lock(cls, acquirer_id=None, auto_renewal=True, expiry_seconds=10):
        return redis_lock.Lock(
            redis_client=strict_redis_client,
            name='{0}__locked'.format(cls.__name__),
            expire=expiry_seconds,
            id=acquirer_id,
            auto_renewal=auto_renewal,
            strict=True)

    @classmethod
    def read_write_lock(cls, suffix=None, auto_renewal=True, expiry_seconds=10, is_write=False):
        name = cls.__name__
        if suffix is not None:
            name += "/eon_{}".format(suffix)
        return ReadWriteLock(strict_redis_client, name, auto_renewal=auto_renewal, expiry_seconds=expiry_seconds, is_write=is_write)
