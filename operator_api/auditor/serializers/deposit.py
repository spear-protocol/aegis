from rest_framework import serializers
from ledger.models import Deposit


class DepositSerializer(serializers.ModelSerializer):
    time = serializers.IntegerField(source='get_timestamp', read_only=True)

    class Meta:
        model = Deposit
        fields = ('txid', 'block', 'eon_number', 'amount', 'time', )
        read_only_fields = fields
