import logging
from django.core.management.base import BaseCommand, CommandError
from eth_utils import add_0x_prefix
from contractor.interfaces import EthereumInterface
from ledger.token_registration import register_token


logging.basicConfig(level=logging.INFO)


def ethereum_address(string):
    return EthereumInterface().web3.toChecksumAddress(add_0x_prefix(string))


class Command(BaseCommand):
    help = 'Register ERC20 Token'

    def add_arguments(self, parser):
        parser.add_argument('token_address', type=ethereum_address)
        parser.add_argument('name', type=str)
        parser.add_argument('short_name', type=str)

    def handle(self, *args, **options):
        try:
            register_token(
                token_address=options['token_address'],
                name=options['name'],
                short_name=options['short_name'],
                register_on_chain=True)
        except ValueError as e:
            raise CommandError(e)
