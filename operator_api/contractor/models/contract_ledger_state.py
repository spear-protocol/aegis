from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from operator_api.models import CleanModel, MutexModel


class ContractLedgerState(CleanModel, MutexModel):
    contract_state = models.ForeignKey(
        to='ContractState',
        on_delete=models.PROTECT)
    token = models.ForeignKey(
        to='ledger.Token',
        on_delete=models.PROTECT)

    pending_withdrawals = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    confirmed_withdrawals = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    deposits = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])
    total_balance = models.DecimalField(
        max_digits=80,
        decimal_places=0,
        validators=[MinValueValidator(Decimal('0'))])

    def confirm(self, confirmed: 'ContractLedgerState'):
        if any([self.contract_state.confirmed,
                self.contract_state.block != confirmed.contract_state.block,
                self.token_id != confirmed.token_id]):
            return False

        self.pending_withdrawals = confirmed.pending_withdrawals
        self.confirmed_withdrawals = confirmed.confirmed_withdrawals
        self.deposits = confirmed.deposits
        self.total_balance = confirmed.total_balance

        self.save()
        return True

    def to_dictionary_form(self):
        return {
            'contract_state_id': self.contract_state_id,
            'token_id': self.token_id,
            'pending_withdrawals': int(self.pending_withdrawals),
            'confirmed_withdrawals': int(self.confirmed_withdrawals),
            'deposits': int(self.deposits),
            'total_balance': int(self.total_balance)
        }

    @staticmethod
    def from_dictionary_form(dictionary, contract_state):
        return ContractLedgerState(
            contract_state=contract_state,
            token_id=int(dictionary.get('token_id')),
            pending_withdrawals=int(dictionary.get('pending_withdrawals')),
            confirmed_withdrawals=int(dictionary.get('confirmed_withdrawals')),
            deposits=int(dictionary.get('deposits')),
            total_balance=int(dictionary.get('total_balance')))
