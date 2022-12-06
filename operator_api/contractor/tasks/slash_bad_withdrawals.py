import logging
import traceback
from operator_api.decorators import notification_on_error
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db.models import Sum, Min
from django.db import transaction
from contractor.interfaces import NOCUSTContractInterface
from contractor.models import EthereumTransaction
from operator_api import crypto
from ledger.context.wallet_transfer import WalletTransferContext
from ledger.models import WithdrawalRequest, MinimumAvailableBalanceMarker, RootCommitment, Wallet

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
@notification_on_error
def slash_bad_withdrawals():
    contract_interface = NOCUSTContractInterface()

    current_eon = contract_interface.get_current_eon_number()

    # This lock is needed because some Withdrawal objects might be mutated, which can affect the checkpoint.
    with RootCommitment.global_lock():
        checkpoint_created = RootCommitment.objects.filter(
            eon_number=current_eon).exists()

        # fetch all wallets that issued a pending withdrawal
        # pending withdrawals that were not slashed yet and issued during this eon or the previous one
        withdrawal_wallets = WithdrawalRequest.objects \
            .filter(slashed=False, eon_number__gte=current_eon-1) \
            .values_list('wallet', flat=True).distinct()

        for wallet_id in withdrawal_wallets:
            # fetch wallet object
            wallet = Wallet.objects.get(id=wallet_id)

            with wallet.lock(auto_renewal=True), transaction.atomic():
                pending_withdrawals = WithdrawalRequest.objects \
                    .filter(wallet=wallet, slashed=False, eon_number__gte=current_eon-1) \
                    .select_for_update()

                # skip slashing if no slashable pending withdrawals are found
                if pending_withdrawals.count() == 0:
                    logger.warning('Skipping withdrawal slash for {}. No Slashable Pending Withdrawals.'
                                   .format(wallet.address))
                    continue

                withdrawal_aggregate_query = pending_withdrawals.aggregate(
                    Sum('amount'), Min('eon_number'))
                withdrawal_amount = withdrawal_aggregate_query['amount__sum']
                min_eon = withdrawal_aggregate_query['eon_number__min']

                withdrawals_in_current_eon = WithdrawalRequest.objects.filter(
                    wallet=wallet, eon_number=current_eon).count()
                # create a tag for the tuple
                # (current eon, number of pending withdrawals in this eon, wallet id, total withdrawal amount )
                tag = 'withdrawal_request_{}_{}_{}_{}' \
                    .format(current_eon, withdrawals_in_current_eon, wallet.id, withdrawal_amount)

                if EthereumTransaction.objects.filter(tag=tag).exists():
                    logger.warning(
                        'Skipping withdrawal slash for address {} and token {}. Slashing transaction already enqueued.'
                        .format(
                            wallet.address,
                            wallet.token.address))
                    continue

                wallet_transfer_context = WalletTransferContext(
                    wallet=wallet, transfer=None)
                available_balance = wallet_transfer_context.loosely_available_funds_at_eon(
                    eon_number=current_eon,
                    current_eon_number=current_eon,
                    is_checkpoint_created=checkpoint_created,
                    only_appended=True)

                if available_balance >= 0:
                    logger.warning(
                        'Skipping withdrawal slash for address {} and token {}. Available balance covers amount.'
                        .format(
                            wallet.address,
                            wallet.token.address))
                    continue

                # find minimum balance marker
                # start before min possible eon
                # until current eon
                minimum_balance = MinimumAvailableBalanceMarker.objects \
                    .filter(
                        wallet=wallet,
                        eon_number__gte=min_eon-1,
                        eon_number__lte=current_eon) \
                    .order_by('amount') \
                    .first()
                if minimum_balance is None or minimum_balance.amount >= withdrawal_amount:
                    logger.warning(
                        'Skipping withdrawal slash for address {} and token {}. Minimum balance within two epochs covers amount.'
                        .format(
                            wallet.address, wallet.token.address))
                    continue

                logger.warning('{}: Slashing withdrawals of {} > {} >= {}.'
                               .format(
                                   wallet.address,
                                   withdrawal_amount,
                                   available_balance,
                                   minimum_balance.amount))

                v, r, s = minimum_balance.signature.vrs()

                # slash all withdrawals for this wallet-token pair
                contract_interface.queue_slash_withdrawal(
                    token_address=wallet.token.address,
                    wallet_address=wallet.address,
                    eon_number=minimum_balance.eon_number,
                    available=int(minimum_balance.amount),
                    r=crypto.uint256(r),
                    s=crypto.uint256(s),
                    v=v,
                    tag=tag)

                # mark all related withdrawals as slashed
                pending_withdrawals.update(slashed=True)
