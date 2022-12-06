from hexbytes import HexBytes

from operator_api.util import Singleton
from ledger.models import Wallet, Deposit, BlacklistEntry
from operator_api.crypto import remove_0x_prefix, hex_address
from celery.utils.log import get_task_logger
from .event import EventInterpreter
from synchronizer.utils import send_notification, CONFIRMED_DEPOSIT
from auditor.serializers import DepositSerializer

logger = get_task_logger(__name__)


class DepositInterpreter(EventInterpreter, metaclass=Singleton):
    def interpret(self, decoded_event, txid, block_number, eon_number, verbose=False):
        wallet_address = hex_address(decoded_event.get(u'recipient'))

        try:
            wallet = Wallet.objects.get(
                token__address__iexact=hex_address(
                    decoded_event.get(u'token')),
                address__iexact=wallet_address)
        except Wallet.DoesNotExist:
            logger.warning(
                "UNKNOWN WALLET PERFORMING DEPOSIT {}".format(wallet_address))
            BlacklistEntry.objects.get_or_create(
                address=wallet_address)
            return

        with wallet.lock(auto_renewal=True):
            deposit = Deposit.objects.create(
                wallet=wallet,
                amount=decoded_event.get(u'amount'),
                eon_number=eon_number,
                block=block_number,
                txid=remove_0x_prefix(txid))

            # send deposit added notification to sender
            send_notification(
                stream_prefix="wallet",
                stream_id="{}/{}".format(wallet.token.address, wallet.address),
                event_name=CONFIRMED_DEPOSIT,
                data=DepositSerializer(
                    deposit, read_only=True).data
            )
