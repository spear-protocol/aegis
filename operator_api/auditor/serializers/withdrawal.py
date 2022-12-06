from rest_framework import serializers
from .withdrawal_request import WithdrawalRequestSerializer
from ledger.models import WithdrawalRequest


class WithdrawalSerializer(serializers.ModelSerializer):
    request = WithdrawalRequestSerializer(read_only=True)
    time = serializers.IntegerField(source='get_timestamp', read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = ('txid', 'block', 'eon_number', 'amount', 'time', 'request')
        read_only_fields = fields
