from django.conf import settings
from django.db import models
import redis
import redis_lock


# parallel read, single write lock
# write biased
class ReadWriteLock():
    @classmethod
    def get_locks(cls, redis_client, name, auto_renewal, expiry_seconds):
        # confirmation lock guarantee consistency when writing
        global_lock = redis_lock.Lock(
            redis_client=redis_client,
            name='{0}/{1}__locked'.format(cls.__name__, name),
            expire=expiry_seconds,
            id=None,
            auto_renewal=auto_renewal,
            strict=True)
        # counter lock guarantee consistency when accessing read counter
        counter_lock = redis_lock.Lock(
            redis_client=redis_client,
            name='{0}/{1}_read_counter__locked'.format(cls.__name__, name),
            expire=expiry_seconds,
            id=None,
            auto_renewal=auto_renewal,
            strict=True)
        # write waiting lock enforces priority of writes over reads
        write_waiting_lock = redis_lock.Lock(
            redis_client=redis_client,
            name='{0}/{1}_write_pending__locked'.format(cls.__name__, name),
            expire=expiry_seconds,
            id=None,
            auto_renewal=auto_renewal,
            strict=True)

        return global_lock, counter_lock, write_waiting_lock

    def __init__(self, redis_client, name, auto_renewal=True, expiry_seconds=10, is_write=False):
        self.auto_renewal = auto_renewal
        self.expiry_seconds = expiry_seconds
        self.is_write = is_write
        self.redis_client = redis_client
        self.read_counter_name = '{0}/{1}_read_counter'.format(
            self.__class__.__name__, name)
        self.global_lock, self.counter_lock, self.write_waiting_lock = self.get_locks(
            redis_client, name, auto_renewal=auto_renewal, expiry_seconds=expiry_seconds)

    def lock(self):
        if self.is_write:
            # single write
            # acquire write pending lock, to stop new reads from acquiring the lock (piling up on counter)
            self.write_waiting_lock.acquire(blocking=True)
            # acquire main lock, to block reads preventing inconsistencies
            self.global_lock.acquire(blocking=True)
        else:
            # parallel reads
            # try to acquire then release write pending lock, to give priority to writes
            self.write_waiting_lock.acquire(blocking=True)
            self.write_waiting_lock.reset()

            # access parallel reads counter
            with self.counter_lock:
                counter = int(self.redis_client.get(
                    self.read_counter_name) or 0)

                # increment counter
                # this will allow reads to pile up and execute if one of them already acquired the lock
                self.redis_client.set(self.read_counter_name, counter+1)

                # if counter is 0, then try to acquire main lock
                # this will block writes if a read is processing
                if counter == 0:
                    self.global_lock.acquire(blocking=True)

    def release(self):
        if self.is_write:
            # single write
            # release pending lock to unblock piled up reads
            self.write_waiting_lock.reset()
            # release main lock to hand control back to reads
            self.global_lock.reset()
        else:
            # parallel reads
            with self.counter_lock:
                counter = int(self.redis_client.get(
                    self.read_counter_name) or 0)

                # decrement counter if it is larger than zero
                if counter > 0:
                    self.redis_client.set(
                        self.read_counter_name, counter-1)

                # if new counter is 0, then all piled up reads are done
                # reset main lock to give back control to writes
                if counter == 1:
                    self.global_lock.reset()

    # syntactic sugar
    # implementing python pattern, to use this lock inside a "with" context statement
    def __enter__(self):
        self.lock()
        return None

    def __exit__(self, type, value, traceback):
        self.release()
