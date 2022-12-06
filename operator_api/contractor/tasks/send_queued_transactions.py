import logging
from operator_api.decorators import notification_on_error
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from eth_utils import add_0x_prefix, remove_0x_prefix

from contractor.interfaces import NOCUSTContractInterface, LocalViewInterface
from contractor.models import EthereumTransaction, EthereumTransactionAttempt
from operator_api.email import send_admin_email

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def send_queued_transactions():
    contract_interface = NOCUSTContractInterface()

    latest_block = LocalViewInterface.latest_block()

    with EthereumTransaction.global_lock(auto_renewal=True):
        pending_transactions = EthereumTransaction.objects.all().order_by('nonce')

        for transaction in pending_transactions:
            if transaction.ethereumtransactionattempt_set.filter(confirmed=True).exists():
                continue

            if transaction.ethereumtransactionattempt_set.exists():
                last_attempt = transaction.ethereumtransactionattempt_set.order_by(
                    'gas_price').last()
            else:
                initial_gas_price = contract_interface.web3.toWei(
                    '100', 'gwei')
                signed_tx = contract_interface.sign_for_delivery_as_owner(
                    transaction, initial_gas_price)
                try:
                    logger.info('Publishing Signed TX: {}'.format(signed_tx))
                    hash = contract_interface.send_raw_transaction(
                        signed_tx.rawTransaction)
                except ValueError as e:
                    logger.error('INITIAL TRANSACTION ATTEMPT ERROR: {}'.format(transaction.tag))
                    logger.error('VALUE ERROR: {}'.format(e))
                    send_admin_email(
                        subject='INITIAL TRANSACTION ATTEMPT ERROR',
                        content='{}: {}'.format(transaction.tag, e))
                    continue
                last_attempt = EthereumTransactionAttempt.objects.create(
                    transaction=transaction,
                    block=latest_block,
                    gas_price=initial_gas_price,
                    signed_attempt=signed_tx.rawTransaction.hex(),
                    hash=remove_0x_prefix(hash.hex()),
                    mined=False,
                    confirmed=False)

            if transaction.ethereumtransactionattempt_set.filter(mined=True).exists():
                try:
                    mined_transaction = transaction.ethereumtransactionattempt_set.get(
                        mined=True)
                except EthereumTransactionAttempt.DoesNotExist:
                    logger.error('Mined Transaction Attempt Inconsistency')
                    continue

                receipt = contract_interface.get_transaction_receipt_hex(
                    add_0x_prefix(mined_transaction.hash))

                if receipt is not None:
                    if receipt.get('blockNumber') - latest_block > settings.HUB_LQD_CONTRACT_CONFIRMATIONS:
                        logger.info('Transaction confirmed! {}'.format(
                            last_attempt.hash))
                        mined_transaction.confirmed = True
                        mined_transaction.save()
                    continue

                logger.warning(
                    'Transaction UNMINED: {}'.format(last_attempt.hash))
                mined_transaction.mined = False
                mined_transaction.save()

            receipt = contract_interface.get_transaction_receipt_hex(
                add_0x_prefix(last_attempt.hash))
            if receipt is not None:
                last_attempt.mined = True
                last_attempt.save()
                continue

            logger.warning('latest_block : {}'.format(latest_block))
            logger.warning('last_attempt.block: {}'.format(last_attempt.block))
            if latest_block - last_attempt.block > 10:
                new_gas_price = 2 * int(last_attempt.gas_price)
                signed_tx = contract_interface.sign_for_delivery_as_owner(
                    transaction, new_gas_price)
                try:
                    hash = contract_interface.send_raw_transaction(
                        signed_tx.rawTransaction)
                except ValueError as e:
                    send_admin_email(
                        subject='TRANSACTION RE-ATTEMPT ERROR',
                        content='{}: {}'.format(transaction.tag, e))
                    continue

                EthereumTransactionAttempt.objects.create(
                    transaction=transaction,
                    block=latest_block,
                    gas_price=new_gas_price,
                    signed_attempt=signed_tx.rawTransaction.hex(),
                    hash=remove_0x_prefix(hash.hex()),
                    mined=False,
                    confirmed=False)

                send_admin_email(
                    subject='Transaction Reattempt',
                    content='{}: {}'.format(transaction.tag, new_gas_price))
