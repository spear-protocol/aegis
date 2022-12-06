import logging
from celery.utils.log import get_task_logger
from contractor.interfaces import NOCUSTContractInterface
from contractor.models import ContractState
from operator_api.celery import operator_celery

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@operator_celery.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=5,
    default_retry_delay=20,
    retry_kwargs={'max_retries': 5, 'default_retry_delay': 20})
def fetch_running_block(self, block_number):
    if ContractState.objects.filter(block=block_number).exists():
        logger.error(
            'Contract state at block {} already exists.'.format(block_number))
        return None
    logger.info('Fetching running block {}.'.format(block_number))
    contract_state, confirmed_contract_ledger_states = NOCUSTContractInterface().fetch_contract_state_at_block(
        block_number=block_number)
    if contract_state is None:
        raise ValueError('No block returned.')
    return contract_state.to_dictionary_form(), [s.to_dictionary_form() for s in confirmed_contract_ledger_states]


@operator_celery.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=5,
    default_retry_delay=20,
    retry_kwargs={'max_retries': 5, 'default_retry_delay': 20})
def fetch_confirmed_block(self, block_number):
    contract_interface = NOCUSTContractInterface()
    logger.info('Fetching confirmed block {}.'.format(block_number))
    block = contract_interface.get_block(block_number)
    if block is None:
        raise ValueError('No block returned.')

    logger.info('Retrieving logs for block {}.'.format(block_number))
    block_logs = [encode_log(log.__dict__)
                  for log in contract_interface.get_logs(block)]
    if block_logs is None:
        raise ValueError('No block logs returned.')

    confirmed_contract_state, confirmed_contract_ledger_states = contract_interface.fetch_contract_state_at_block(
        block_number=block_number)

    return confirmed_contract_state.to_dictionary_form(), [s.to_dictionary_form() for s in confirmed_contract_ledger_states], block_logs


def encode_log(log: dict):
    return {
        'address': log.get('address'),
        'topics': [value.hex() for value in log.get('topics')],
        'data': log.get('data'),
        'blockNumber': log.get('blockNumber'),
        'transactionHash': log.get('transactionHash').hex(),
        'transactionIndex': log.get('transactionIndex'),
        'blockHash': log.get('blockHash').hex(),
        'logIndex': log.get('logIndex'),
        'removed': log.get('removed')
    }
