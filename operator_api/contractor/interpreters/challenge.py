from eth_utils import remove_0x_prefix
from hexbytes import HexBytes

from operator_api.crypto import hex_address
from operator_api.email import send_admin_email
from operator_api.util import Singleton
from ledger.models import Wallet, Challenge, Token, TokenPair
from .event import EventInterpreter
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def send_address_not_found_log(who, address):
    logger.error("CHALLENGE ISSUED AGAINST UNKNOWN {} {}".format(who, address))
    send_admin_email(
        subject='DISPUTE! UNKNOWN {}!'.format(who),
        content='{}'.format(address))


class ChallengeInterpreter(EventInterpreter, metaclass=Singleton):
    def interpret(self, decoded_event, txid, block_number, eon_number, verbose=False):
        sender_address = hex_address(decoded_event.get(u'sender'))
        recipient_address = hex_address(decoded_event.get(u'recipient'))
        token_address = hex_address(decoded_event.get(u'token'))

        # delivery or state challenge
        try:
            token = Token.objects.get(address__iexact=token_address)

            try:
                wallet = Wallet.objects.get(
                    address__iexact=sender_address, token=token)
            except Wallet.DoesNotExist:
                send_address_not_found_log("SENDER", sender_address)
                return

            try:
                recipient = Wallet.objects.get(
                    address__iexact=recipient_address, token=token)
            except Wallet.DoesNotExist:
                send_address_not_found_log("RECIPIENT", sender_address)
                return

        # swap challenge
        except Token.DoesNotExist:

            try:
                token_pair = TokenPair.objects.get(
                    conduit__iexact=token_address)
            except TokenPair.DoesNotExist:
                send_address_not_found_log(
                    "TOKEN PAIR WITH CONDUIT", token_address)
                return

            try:
                wallet = Wallet.objects.get(
                    address__iexact=sender_address, token=token_pair.token_from)
            except Wallet.DoesNotExist:
                send_address_not_found_log("SENDER", sender_address)
                return

            try:
                recipient = Wallet.objects.get(
                    address__iexact=recipient_address, token=token_pair.token_to)
            except Wallet.DoesNotExist:
                send_address_not_found_log("RECIPIENT", sender_address)
                return

        Challenge.objects.create(
            wallet=wallet,
            recipient=recipient,
            amount=0,
            eon_number=eon_number,
            block=block_number,
            txid=remove_0x_prefix(txid))
