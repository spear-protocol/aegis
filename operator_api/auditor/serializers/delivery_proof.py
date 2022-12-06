from rest_framework import serializers

from ledger.context.wallet_transfer import WalletTransferContext
from operator_api.util import long_string_to_list, csf_to_list
from .proof import ProofSerializer
from ledger.models import Transfer


class DeliveryProofSerializer(serializers.Serializer):
    merkle_proof = ProofSerializer(read_only=True)
    transfer_membership_chain = serializers.ListField(
        child=serializers.CharField(max_length=66), read_only=True)
    transfer_membership_trail = serializers.IntegerField(
        min_value=0, read_only=True)
    transfer_membership_values = serializers.ListField(child=serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0), read_only=True)

    class Meta:
        swagger_schema_fields = {
            'title': 'DeliveryProof'
        }

    def to_representation(self, transfer: Transfer):
        if transfer.final_receipt_hashes is None:
            return {}

        # include proof if
        # 1) context wallet_id is provided and parent is sender wallet
        # 2) context wallet_id is None
        include_proof = self.context.get('wallet_id') is None or self.context.get(
            'wallet_id') == transfer.wallet.id

        if include_proof:
            recipient_balance = WalletTransferContext(
                wallet=transfer.recipient, transfer=transfer).balance_as_of_eon(transfer.eon_number + 1)

        return {
            'merkle_proof': ProofSerializer(recipient_balance, read_only=True).data if include_proof else None,
            'transfer_membership_chain':
                long_string_to_list(transfer.final_receipt_hashes, 64),
            'transfer_membership_trail':
                int(transfer.final_receipt_index),
            'transfer_membership_values':
                csf_to_list(
                    transfer.final_receipt_values) if transfer.passive else None
        }
