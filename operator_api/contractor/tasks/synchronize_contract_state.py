from operator_api.decorators import notification_on_error
import logging
import traceback
import sys
from celery import shared_task, exceptions
from django.conf import settings
from celery.utils.log import get_task_logger
from django.db import transaction

from contractor.interfaces import NOCUSTContractInterface, LocalViewInterface
from contractor.decoders import NOCUSTContractEventDecoder
from contractor.interpreters import event_interpreter_map
from contractor.models import ContractState, ContractLedgerState
from contractor.tasks.fetch_blocks import fetch_running_block, fetch_confirmed_block
from operator_api.email import send_admin_email

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


def fully_synchronize_contract_state(verbose=False):
    while synchronize_contract_state(verbose) > 0:
        pass


@shared_task
@notification_on_error
def synchronize_contract_state(verbose=False):
    logger.info('Retrieving confirmed events')

    if not LocalViewInterface.get_contract_parameters():
        logger.error('Contract parameters not yet populated.')
        return

    with ContractState.global_lock():
        logger.info('Start..')
        contract_interface = NOCUSTContractInterface()
        logger.info('Interface acquired')
        contract_event_decoder = NOCUSTContractEventDecoder()
        logger.info('Decoder acquired')
        contract_interface.get_blocks_per_eon()

        return concurrently_retrieve_state(contract_interface, contract_event_decoder, verbose)


def concurrently_retrieve_state(contract_interface, contract_event_decoder, verbose):
    logger.info('Retrieve blocks.')
    latest_chain_block = contract_interface.current_block() - 1
    if not settings.DEBUG:
        latest_chain_block += 1

    logger.info('Latest chain block: {}'.format(latest_chain_block))

    running_from = LocalViewInterface.latest_block() + 1
    running_until = latest_chain_block

    if running_from > running_until:
        logger.info('No new blocks {}-{}.'.format(running_from, running_until))
        return 0

    confirm_from = LocalViewInterface.confirmed_block() + 1
    confirm_until = running_until - contract_interface.get_blocks_for_confirmation()

    if confirm_from > confirm_until:
        logger.info('No new blocks to confirm.')

    update_from = min(running_from, confirm_from)
    update_until = min(update_from + 11, running_until + 1)
    skipped = running_until + 1 - update_until

    contract_state_tasks = []
    contract_state_tasks_block_numbers = []

    logger.info('Fetching [{},{})'.format(update_from, update_until))
    for block_number in range(update_from, update_until):
        if confirm_from <= block_number and block_number <= confirm_until:
            contract_state_tasks.append(
                fetch_confirmed_block.delay(block_number=block_number))
            contract_state_tasks_block_numbers.append(block_number)
        elif running_from <= block_number and block_number <= running_until:
            contract_state_tasks.append(
                fetch_running_block.delay(block_number=block_number))
            contract_state_tasks_block_numbers.append(block_number)

    for task_index, contract_state_task in enumerate(contract_state_tasks):
        block_number = contract_state_tasks_block_numbers[task_index]

        try:
            task_result = contract_state_task.get(
                timeout=settings.HUB_BLOCK_FETCH_TIMEOUT,
                disable_sync_subtasks=False)
        except exceptions.TimeoutError:
            logger.error('Timed-out fetching block {}'.format(block_number))
            for cleanup_index, task_to_clean_up in enumerate(contract_state_tasks):
                if cleanup_index >= task_index:
                    try:
                        task_to_clean_up.forget()
                    except NotImplementedError as e:
                        logger.error('Could not forget task results.')
                        logger.error(e)
            break

        if confirm_from <= block_number and block_number <= confirm_until:
            confirmed_contract_state_dictionary, confirmed_contract_ledger_state_dictionaries, block_logs = task_result

            confirmed_contract_state = ContractState.from_dictionary_form(
                confirmed_contract_state_dictionary)
            confirmed_ledger_states = [ContractLedgerState.from_dictionary_form(ledger_state, confirmed_contract_state) for ledger_state in
                                       confirmed_contract_ledger_state_dictionaries]
            with transaction.atomic():
                if running_from <= block_number and block_number <= running_until:
                    confirmed_contract_state.save()
                    for ledger_state in confirmed_ledger_states:
                        ledger_state.contract_state = confirmed_contract_state
                        ledger_state.save()

                logger.info('Decoding logs for block {}.'.format(
                    confirmed_contract_state.block))
                decoded_logs = contract_event_decoder.decode_many(block_logs)
                eon_number = confirmed_contract_state.eon_number()
                logger.info("Processing decoded logs in block %d eon %s: %d logs" % (
                    confirmed_contract_state.block, eon_number, len(decoded_logs)))
                for log in decoded_logs:

                    if log.get(u'name') in event_interpreter_map:
                        interpreter = event_interpreter_map.get(
                            log.get(u'name'))
                        interpreter.interpret(
                            decoded_event=log.get('data'),
                            txid=log.get('txid'),
                            block_number=confirmed_contract_state.block,
                            eon_number=eon_number,
                            verbose=verbose) if interpreter else None
                    else:
                        logger.error('UNKNOWN EVENT LOG {} '.format(log))
                        send_admin_email(
                            subject='Chain Sync Error: Unknown Log',
                            content='{}'.format(log))

                running_contract_state = LocalViewInterface.running(
                    block_number=confirmed_contract_state.block)

                if running_contract_state.confirm(confirmed_contract_state, confirmed_ledger_states):
                    logger.info('Block {} confirmed.'.format(
                        confirmed_contract_state.block))
                else:
                    logger.error('Block {} failed to confirm.'.format(
                        confirmed_contract_state.block))
                    send_admin_email(
                        subject='Chain Sync Confirmation Failure {}'.format(
                            confirmed_contract_state.block),
                        content='{}'.format(confirmed_contract_state))
                    raise Exception()
        elif running_from <= block_number and block_number <= running_until:
            logger.info('Process running block {}'.format(block_number))
            confirmed_contract_state_dictionary, confirmed_contract_ledger_state_dictionaries = task_result

            contract_state = ContractState.from_dictionary_form(
                confirmed_contract_state_dictionary)
            contract_state.save()
            ledger_states = [ContractLedgerState.from_dictionary_form(ledger_state, contract_state) for ledger_state in
                             confirmed_contract_ledger_state_dictionaries]
            for ledger_state in ledger_states:
                ledger_state.save()
            logger.info('Running block {} stored.'.format(
                contract_state.block))
        else:
            logger.info('Running from {} to {}.'.format(
                running_from, running_until))
            logger.info('Confirm from {} to {}.'.format(
                confirm_from, confirm_until))
            logger.info('Update from {} to {}.'.format(
                update_from, update_until))
            logger.error('Unexpected block number {}'.format(block_number))
            send_admin_email(
                subject='Chain Sync Unexpected Block {}'.format(block_number),
                content='Out of order processing.')
            raise Exception()
    return skipped
