from hexbytes import HexBytes

from operator_api.util import Singleton
from ledger.models import Wallet, WithdrawalRequest, Withdrawal
from operator_api.crypto import remove_0x_prefix, hex_address
from celery.utils.log import get_task_logger
from .event import EventInterpreter
from synchronizer.utils import send_notification, CONFIRMED_WITHDRAWAL
from auditor.serializers import WithdrawalSerializer


logger = get_task_logger(__name__)


class WithdrawalConfirmationInterpreter(EventInterpreter, metaclass=Singleton):
    def interpret(self, decoded_event, txid, block_number, eon_number, verbose=False):
        token_address = decoded_event.get(u'token')
        wallet_address = decoded_event.get(u'requestor')
        amount = decoded_event.get(u'amount')

        try:
            wallet = Wallet.objects.get(
                token__address__iexact=hex_address(token_address),
                address__iexact=hex_address(wallet_address))
        except Wallet.DoesNotExist:
            return

        # get all unconfirmed unslashed withdrawal requests for this wallet
        # sorted in ascending order by the date they were added
        unslashed_unconfirmed_requests = WithdrawalRequest.objects \
            .filter(wallet=wallet, slashed=False, withdrawal__isnull=True) \
            .order_by('id')

        withdrawal_requests = []
        accumulator = 0

        # add withdrawal requests until confirmation amount is reached
        # from older to newer requests
        for withdrawal_request in unslashed_unconfirmed_requests:
            if accumulator < amount:
                withdrawal_requests.append(withdrawal_request)
                accumulator += withdrawal_request.amount
            else:
                break

        # if accumulator is not equal to confirmed amount there is something very wrong going on
        if accumulator != amount:
            logger.error(
                'CONFIRMED WITHDRAWALS BY {} FOR TOKEN {} DID NOT SUM UP TO EXPECTED AMOUNT {}'
                .format(hex_address(wallet_address), hex_address(token_address), amount))

        # create a withdrawal object for every confirmed withdrawal request
        for withdrawal_request in withdrawal_requests:
            confirmation = Withdrawal(
                wallet=wallet,
                amount=withdrawal_request.amount,
                eon_number=eon_number,
                request=withdrawal_request,
                block=block_number,
                txid=remove_0x_prefix(txid))

            # send withdrawal confirmed notification to wallet
            send_notification(
                stream_prefix="wallet",
                stream_id="{}/{}".format(wallet.token.address, wallet.address),
                event_name=CONFIRMED_WITHDRAWAL,
                data=WithdrawalSerializer(
                    confirmation, read_only=True).data
            )

            if verbose:
                print(withdrawal_request)
                print(confirmation)

            confirmation.save()
