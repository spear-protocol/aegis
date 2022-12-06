import logging
from operator_api.decorators import notification_on_error
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from contractor.interfaces import NOCUSTContractInterface
from contractor.models import EthereumTransaction
from ledger.models import WithdrawalRequest, Wallet

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def confirm_withdrawals():
    contract_interface = NOCUSTContractInterface()
    current_eon = contract_interface.get_current_eon_number()
    if contract_interface.get_current_subblock() < contract_interface.get_extended_slack_period():
        return

    # fetch all wallets that issued a pending withdrawal
    # pending withdrawals that were not slashed yet and issued 2 eons ago
    withdrawal_wallets = WithdrawalRequest.objects.filter(slashed=False, eon_number=current_eon-2).select_related('wallet__token')
    withdrawal_wallets = {(x.wallet, x.wallet.token) for x in withdrawal_wallets}

    for wallet_tuple in withdrawal_wallets:
        wallet = wallet_tuple[0]
        token = wallet_tuple[1]
        # create a tag for the tuple (current eon, wallet id)
        tag = f'withdrawal_confirmation_{current_eon}_{wallet.id}'

        # skip confirmation if it is already enqueued
        if EthereumTransaction.objects.filter(tag=tag).exists():
            logger.warning(
                'Skipping withdrawal confirmation for address {} and token {}. Confirmation transaction already enqueued.'
                .format(
                    wallet.address,
                    token.address))
            continue

        # confirm withdrawals
        contract_interface.queue_confirm_withdrawal(
            token.address, wallet.address, tag)
