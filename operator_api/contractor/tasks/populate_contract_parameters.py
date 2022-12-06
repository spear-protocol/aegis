import logging
from celery import shared_task
from celery.utils.log import get_task_logger
from contractor.interfaces import NOCUSTContractInterface
from contractor.models import ContractParameters, ContractState
from operator_api.util import ZERO_CHECKSUM

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@shared_task
def populate_contract_parameters():
    logger.info('Populating contract parameters.')
    if ContractParameters.objects.all().exists():
        logger.warning('Contract parameters already populated.')
        return

    contract_interface = NOCUSTContractInterface()

    with ContractParameters.global_lock():
        try:
            genesis_block = contract_interface.get_genesis_block()
            ContractParameters.objects.create(
                genesis_block=genesis_block,
                eons_kept=contract_interface.get_eons_kept(),
                blocks_per_eon=contract_interface.get_blocks_per_eon(),
                challenge_cost=contract_interface.get_challenge_min_gas_cost())
            ContractState.objects.create(
                block=genesis_block,
                confirmed=False,
                basis=ZERO_CHECKSUM,
                last_checkpoint_submission_eon=0,
                last_checkpoint=ZERO_CHECKSUM,
                is_checkpoint_submitted_for_current_eon=False,
                has_missed_checkpoint_submission=False,
                live_challenge_count=0)
            logger.info('Contract parameters populated.')
        except ValueError as value_error:
            logger.error(
                'Could not populate contract parameters: {}'.format(value_error))
