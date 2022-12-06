import logging

from multiprocessing.pool import Pool
from celery.utils.log import get_task_logger, current_process
from django.conf import settings
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


def get_transaction_receipt(txid):
    return EthereumInterface().get_transaction_receipt(txid)


class EthereumInterface:
    def __init__(self):
        self.web3 = Web3(HTTPProvider(settings.HUB_ETHEREUM_NODE_URL))
        if settings.HUB_ETHEREUM_NETWORK_IS_POA:
            self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    def get_chain_id(self):
        return int(self.web3.net.version)

    def get_account_balance(self, address, block_number='latest'):
        return self.web3.eth.getBalance(address, block_identifier=block_number)

    def get_block(self, block_number):
        return self.web3.eth.getBlock(block_number)

    def current_block(self):
        return self.web3.eth.getBlock('latest').get('number')

    def get_transaction_receipt(self, txid):
        return self.web3.eth.getTransactionReceipt(txid.hex())

    def get_transaction_receipt_hex(self, transaction_hash):
        return self.web3.eth.getTransactionReceipt(transaction_hash)

    def get_logs(self, block):
        result = []
        if block and block.get(u'hash'):
            for txid in block.get(u'transactions'):
                receipt = self.get_transaction_receipt(txid)
                if receipt is None:
                    logger.error('No receipt for txid {}'.format(txid))
                elif receipt.get(u'logs'):
                    result.extend(receipt.get(u'logs'))
        return result

    def concurrently_get_logs(self, block):
        result = []
        if block and block.get(u'hash'):
            logger.info('Retrieving receipts in parallel')

            # TODO remove this hack when celery/billiard comes to its senses..
            old_val = current_process()._config.get('daemon')
            current_process()._config['daemon'] = False
            with Pool(processes=10) as p:
                receipts = p.map(get_transaction_receipt,
                                 block.get(u'transactions'))
            logger.info('{} receipts retrieved.'.format(len(receipts)))
            current_process()._config['daemon'] = old_val

            for receipt in receipts:
                if receipt.get(u'logs'):
                    result.extend(receipt.get(u'logs'))
        return result

    def send_raw_transaction(self, transaction):
        logger.info('Publishing Raw Transaction: {}'.format(transaction))
        #return self.web3.eth.sendRawTransaction(self.web3.toHex(transaction))
        return self.web3.eth.sendRawTransaction(transaction)
