from rest_framework import serializers
from operator_api.util import long_string_to_list, csf_to_list, str_int
from operator_api.crypto import encode_hex
from ledger.models import ExclusiveBalanceAllotment
from ledger.context.wallet_transfer import WalletTransferContext
from .active_state import ConciseActiveStateSerializer


class ProofSerializer(serializers.Serializer):
    eon_number = serializers.IntegerField(min_value=0, read_only=True)
    left = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    right = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    allotment_chain = serializers.ListField(
        child=serializers.CharField(max_length=66), read_only=True)
    membership_chain = serializers.ListField(
        child=serializers.CharField(max_length=66), read_only=True)
    values = serializers.ListField(child=serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0), read_only=True)
    trail = serializers.IntegerField(min_value=0, read_only=True)
    active_state_checksum = serializers.CharField(
        max_length=66, read_only=True)
    active_state = ConciseActiveStateSerializer(read_only=True)
    passive_checksum = serializers.CharField(max_length=66, read_only=True)
    passive_amount = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    passive_marker = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)

    class Meta:
        swagger_schema_fields = {
            'title': 'Proof'
        }

    def to_representation(self, instance: ExclusiveBalanceAllotment):
        wallet_context = WalletTransferContext(
            wallet=instance.wallet, transfer=None)
        passive_checksum, passive_amount, passive_marker = wallet_context.get_passive_values(
            eon_number=instance.eon_number - 1)
        return {
            'eon_number': int(instance.eon_number),
            'left': str_int(instance.left),
            'right': str_int(instance.right),
            'allotment_chain': long_string_to_list(instance.merkle_proof_hashes, 64),
            'membership_chain': long_string_to_list(instance.merkle_membership_chain(), 64),
            'values': csf_to_list(instance.merkle_proof_values, str_int),
            'trail': int(instance.merkle_proof_trail),
            'active_state_checksum':
                encode_hex(instance.active_state.checksum()) if instance.active_state else
                encode_hex(b'\0'*32),
            'active_state':
                ConciseActiveStateSerializer(
                    instance.active_state, read_only=True).data if instance.active_state else None,
            'passive_checksum': encode_hex(passive_checksum),
            'passive_amount': str_int(passive_amount),
            'passive_marker': str_int(passive_marker)
        }
