from rest_framework import serializers
from ledger.models import Transfer, Deposit, WithdrawalRequest, Withdrawal
from django.db.models import Q
from .admission import AdmissionSerializer
from .proof import ProofSerializer
from .transfer import TransactionSerializer
from .deposit import DepositSerializer
from .withdrawal import WithdrawalSerializer
from .withdrawal_request import WithdrawalRequestSerializer


class WalletStateSerializer(serializers.Serializer):
    registration = AdmissionSerializer(read_only=True)
    merkle_proof = ProofSerializer(read_only=True)
    transactions = TransactionSerializer(many=True, read_only=True)
    deposits = DepositSerializer(many=True, read_only=True)
    withdrawal_requests = WithdrawalRequestSerializer(
        many=True, read_only=True)
    withdrawals = WithdrawalSerializer(many=True, read_only=True)

    def to_representation(self, wallet_data_request):
        balance = wallet_data_request.wallet\
            .exclusivebalanceallotment_set\
            .filter(eon_number=wallet_data_request.eon_number).last()
        transactions = Transfer.objects\
            .filter(eon_number=wallet_data_request.eon_number, id__gte=wallet_data_request.transfer_id)\
            .filter(Q(wallet=wallet_data_request.wallet) | Q(recipient=wallet_data_request.wallet))\
            .select_related('recipient')\
            .select_related('wallet')\
            .select_related('recipient__token')\
            .select_related('wallet__token')\
            .order_by('id')
        deposits = Deposit.objects \
            .filter(wallet=wallet_data_request.wallet)\
            .filter(eon_number=wallet_data_request.eon_number) \
            .order_by('id')
        withdrawal_requests = WithdrawalRequest.objects \
            .filter(wallet=wallet_data_request.wallet)\
            .filter(eon_number=wallet_data_request.eon_number) \
            .order_by('id')
        withdrawals = Withdrawal.objects \
            .filter(wallet=wallet_data_request.wallet)\
            .filter(eon_number=wallet_data_request.eon_number) \
            .order_by('id')

        return {
            'registration':
                AdmissionSerializer(
                    wallet_data_request.wallet, read_only=True).data,
            'merkle_proof':
                ProofSerializer(
                    balance, read_only=True).data if balance is not None else None,
            'transactions':
                TransactionSerializer(transactions, context={
                    'wallet_id': wallet_data_request.wallet.id}, many=True, read_only=True).data,
            'deposits':
                DepositSerializer(deposits, many=True, read_only=True).data,
            'withdrawal_requests':
                WithdrawalRequestSerializer(
                    withdrawal_requests, many=True, read_only=True).data,
            'withdrawals':
                WithdrawalSerializer(
                    withdrawals, many=True, read_only=True).data
        }
