from hexbytes import HexBytes

from operator_api.util import Singleton
from ledger.models import Wallet, WithdrawalRequest
from operator_api.crypto import remove_0x_prefix, hex_address
from contractor.interfaces import NOCUSTContractInterface
from celery.utils.log import get_task_logger
from .event import EventInterpreter
from synchronizer.utils import send_notification, REQUESTED_WITHDRAWAL
from auditor.serializers import WithdrawalRequestSerializer

logger = get_task_logger(__name__)


class WithdrawalRequestInterpreter(EventInterpreter, metaclass=Singleton):
    def interpret(self, decoded_event, txid, block_number, eon_number, verbose=False):
        try:
            wallet = Wallet.objects.get(
                token__address__iexact=hex_address(
                    decoded_event.get(u'token')),
                address__iexact=hex_address(decoded_event.get(u'requestor')))
        except Wallet.DoesNotExist:
            # TODO this is a problem
            logger.error("UNKNOWN WALLET REQUESTING WITHDRAWAL {}".format(
                hex_address(decoded_event.get(u'requestor'))))
            return

        with wallet.lock(auto_renewal=True):
            withdrawal_request = WithdrawalRequest.objects.create(
                wallet=wallet,
                amount=decoded_event.get(u'amount'),
                eon_number=eon_number,
                block=block_number,
                txid=remove_0x_prefix(txid))

            # send withdrawal requested notification to wallet
            send_notification(
                stream_prefix="wallet",
                stream_id="{}/{}".format(wallet.token.address, wallet.address),
                event_name=REQUESTED_WITHDRAWAL,
                data=WithdrawalRequestSerializer(
                    withdrawal_request, read_only=True).data
            )

        logger.warning(withdrawal_request)

        if verbose:
            print(withdrawal_request)
