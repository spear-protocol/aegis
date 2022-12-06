from rest_framework import serializers
from ledger.models import ActiveState


class ConciseActiveStateSerializer(serializers.ModelSerializer):
    wallet_signature = serializers.CharField(max_length=130, read_only=True)
    operator_signature = serializers.CharField(max_length=130, read_only=True)
    updated_spendings = serializers.CharField(max_length=80, read_only=True)
    updated_gains = serializers.CharField(max_length=80, read_only=True)
    tx_set_hash = serializers.CharField(max_length=64, read_only=True)

    class Meta:
        model = ActiveState
        swagger_schema_fields = {
            'title': 'ConciseActiveState'
        }
        fields = (
            'wallet_signature',
            'operator_signature',
            'updated_spendings',
            'updated_gains',
            'tx_set_hash')


class ActiveStateSerializer(ConciseActiveStateSerializer):
    tx_set_proof = serializers.ListField(child=serializers.CharField(
        max_length=64), source='tx_set_proof_hashes_formatted', read_only=True)
    tx_set_index = serializers.IntegerField(read_only=True)

    class Meta:
        model = ActiveState
        swagger_schema_fields = {
            'title': 'ActiveState'
        }
        fields = ConciseActiveStateSerializer.Meta.fields + \
            ('tx_set_proof', 'tx_set_index')
