from rest_framework import serializers
from ledger.models import WithdrawalRequest


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    time = serializers.IntegerField(source='get_timestamp', read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = ('txid', 'block', 'eon_number', 'amount', 'time', 'slashed')
        read_only_fields = fields
