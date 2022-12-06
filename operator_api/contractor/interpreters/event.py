from abc import ABCMeta, abstractmethod
from celery.utils.log import get_task_logger
from hexbytes import HexBytes

logger = get_task_logger(__name__)


class EventInterpreter(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def interpret(self, decoded_event, txid, block_number, eon_number, verbose=False):
        pass
