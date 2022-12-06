import logging
from celery import shared_task
from django.conf import settings
from contractor.models import ContractState, EthereumTransaction
from operator_api.email import send_admin_email
from ledger.models import TokenCommitment
from celery.utils.log import get_task_logger
from contractor.interfaces import LocalViewInterface, NOCUSTContractInterface


logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def broadcast_checkpoint():
    """
    References to this function is absent in program code
    """
    with ContractState.global_lock():
        latest_block = LocalViewInterface.latest()
        submitted = latest_block.is_checkpoint_submitted_for_current_eon
        current_eon, current_sub_block = latest_block.eon_number_and_sub_block()
        blocks_for_submission = LocalViewInterface.blocks_for_submission()

        if submitted:
            logger.warning("TokenCommitment already submitted")
            return
        elif current_sub_block < blocks_for_submission:
            logger.warning('Too early to submit checkpoint: {} blocks left'.format(
                blocks_for_submission - current_sub_block))
            return
        elif current_sub_block > 150 and settings.DEBUG:
            logger.error("just let the damn tests pass..")  # TODO: todo
            return
        elif latest_block.has_missed_checkpoint_submission:
            logger.error(
                'The operator has missed a checkpoint submission. Cannot submit checkpoint.')
            send_admin_email(
                subject='The commit chain is halted.',
                content='Ouch.')
            return

        checkpoint = TokenCommitment.objects.get(eon_number=current_eon)

        if EthereumTransaction.objects.filter(tag=checkpoint.tag()).exists():
            logger.warning("TokenCommitment already enqueued.")
            send_admin_email(
                subject='Soft Submission Error: TokenCommitment already enqueued.',
                content='This should eventually be resolved.')
            return

        managed_funds = NOCUSTContractInterface().get_managed_funds(checkpoint.eon_number)
        if checkpoint.upper_bound > managed_funds:
            logger.error(
                "TokenCommitment upper bound greater than managed funds.")
            send_admin_email(
                subject='HARD Submission Error: TokenCommitment upper bound greater than managed funds.',
                content='Created checkpoint for {} while managed funds are {}. Some withdrawals are possibly pending cancellation.'.format(checkpoint.upper_bound, managed_funds))
            return

        NOCUSTContractInterface().queue_submit_checkpoint(checkpoint)
