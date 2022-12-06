import logging

from celery import shared_task
from celery.utils.log import get_task_logger

from admission.tasks import process_admissions
from contractor.tasks import synchronize_contract_state, slash_bad_withdrawals, confirm_withdrawals, respond_to_challenges, send_queued_transactions
from ledger.tasks import create_checkpoint
from swapper.tasks.cancel_finalize_swaps import cancel_finalize_swaps
from swapper.tasks.confirm_swaps import confirm_swaps
from swapper.tasks.process_swaps import process_swaps
from transactor.tasks import process_passive_transfers

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)

# hearbeat for parent-chain verifier management
@shared_task
def heartbeat_verifier():
    # synchronize with contract
    synchronize_contract_state()

    # respond to challenges
    respond_to_challenges()

    # confirm withdrawals
    confirm_withdrawals()

    # broadcast on-chain transactions
    send_queued_transactions()


# heartbeat for account management
@shared_task
def heartbeat_accounting():
    # wallet admissions
    process_admissions()

    # withdrawal slashing
    slash_bad_withdrawals()

    # processing transfers
    # depends on admission
    process_passive_transfers()
    confirm_swaps()
    cancel_finalize_swaps()
    process_swaps()

    # checkpoint creation
    # depends on admission, withdrawal slashing & transfer processing
    create_checkpoint()

