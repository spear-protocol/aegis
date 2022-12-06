import logging

from django.db import models
from django.apps import apps

from .contract_ledger_state import ContractLedgerState
from operator_api.models import CleanModel, MutexModel
from django.db import transaction, IntegrityError

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


class ContractState(CleanModel, MutexModel):
    block = models.BigIntegerField(
        unique=True)
    confirmed = models.BooleanField(
        default=False)

    basis = models.CharField(
        max_length=64)

    last_checkpoint_submission_eon = models.BigIntegerField()
    last_checkpoint = models.CharField(
        max_length=64)
    is_checkpoint_submitted_for_current_eon = models.BooleanField()

    has_missed_checkpoint_submission = models.BooleanField()
    live_challenge_count = models.BigIntegerField()

    def eon_number_and_sub_block(self):
        ContractParameters = apps.get_model('contractor', 'ContractParameters')
        parameters = ContractParameters.objects.first()
        if not parameters:
            return 0, 0

        blocks_passed = self.block - parameters.genesis_block
        return blocks_passed // parameters.blocks_per_eon + 1, blocks_passed % parameters.blocks_per_eon

    def eon_number(self):
        return self.eon_number_and_sub_block()[0]

    def sub_block(self):
        return self.eon_number_and_sub_block()[1]

    def confirm(self, confirmed_state: 'ContractState', confirmed_ledger_states: '[ContractLedgerState]'):
        if self.confirmed or not self.block == confirmed_state.block:
            return False

        self.basis = confirmed_state.basis
        self.last_checkpoint_submission_eon = confirmed_state.last_checkpoint_submission_eon
        self.last_checkpoint = confirmed_state.last_checkpoint
        self.is_checkpoint_submitted_for_current_eon = confirmed_state.is_checkpoint_submitted_for_current_eon
        self.has_missed_checkpoint_submission = confirmed_state.has_missed_checkpoint_submission
        self.live_challenge_count = confirmed_state.live_challenge_count

        with transaction.atomic():
            if len(confirmed_ledger_states) < self.contractledgerstate_set.count():
                raise IntegrityError('Ledger State count mismatch {}/{}'.format(len(confirmed_ledger_states),
                                                                                self.contractledgerstate_set.count()))

            for confirmed_ledger_state in confirmed_ledger_states:
                try:
                    ledger_state = self.contractledgerstate_set.get(
                        token_id=confirmed_ledger_state.token_id)
                    if not ledger_state.confirm(confirmed_ledger_state):
                        raise IntegrityError(
                            'Could not confirm contract ledger state {}'.format(ledger_state.token.address))
                except ContractLedgerState.DoesNotExist:
                    confirmed_ledger_state.contract_state = self
                    confirmed_ledger_state.save()
                    logger.warning(
                        'Could not find contract ledger state {} to confirm.'.format(
                            confirmed_ledger_state.token.address))

            self.confirmed = True
            self.save()

        return True

    def to_dictionary_form(self):
        return {
            'id': self.id,
            'block': int(self.block),
            'confirmed': bool(self.confirmed),
            'basis': str(self.basis),
            'last_checkpoint_submission_eon': int(self.last_checkpoint_submission_eon),
            'last_checkpoint': str(self.last_checkpoint),
            'is_checkpoint_submitted_for_current_eon': bool(self.is_checkpoint_submitted_for_current_eon),
            'has_missed_checkpoint_submission': bool(self.has_missed_checkpoint_submission),
            'live_challenge_count': int(self.live_challenge_count),
        }

    @staticmethod
    def from_dictionary_form(dictionary):
        return ContractState(
            block=int(dictionary.get('block')),
            confirmed=bool(dictionary.get('confirmed')),
            basis=str(dictionary.get('basis')),
            last_checkpoint_submission_eon=int(
                dictionary.get('last_checkpoint_submission_eon')),
            last_checkpoint=str(dictionary.get('last_checkpoint')),
            is_checkpoint_submitted_for_current_eon=bool(
                dictionary.get('is_checkpoint_submitted_for_current_eon')),
            has_missed_checkpoint_submission=bool(
                dictionary.get('has_missed_checkpoint_submission')),
            live_challenge_count=int(dictionary.get('live_challenge_count')))
