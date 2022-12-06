from rest_framework import serializers

from auditor.serializers import SwapMatchedAmountSerializer
from .wallet import WalletSerializer
from .delivery_proof import DeliveryProofSerializer
from .active_state import ActiveStateSerializer
from ledger.models import Transfer
from eth_utils import add_0x_prefix
from drf_yasg.utils import swagger_serializer_method


class TransactionSerializer(serializers.ModelSerializer):
    wallet = WalletSerializer(
        read_only=True)
    recipient = WalletSerializer(
        read_only=True)
    sender_active_state = ActiveStateSerializer(
        read_only=True)
    recipient_active_state = ActiveStateSerializer(
        read_only=True)
    recipient_fulfillment_active_state = ActiveStateSerializer(
        read_only=True)
    recipient_finalization_active_state = ActiveStateSerializer(
        read_only=True)
    swap_freezing_signature = serializers.CharField(
        max_length=130,
        read_only=True)
    sender_cancellation_active_state = ActiveStateSerializer(
        read_only=True)
    sender_finalization_active_state = ActiveStateSerializer(
        read_only=True)
    recipient_cancellation_active_state = ActiveStateSerializer(
        read_only=True)
    delivery_proof = serializers.SerializerMethodField()
    matched_amounts = SwapMatchedAmountSerializer(
        source='*',
        read_only=True)

    time = serializers.IntegerField(
        source='get_timestamp',
        read_only=True)

    # pass through context wallet_id
    @swagger_serializer_method(serializer_or_field=DeliveryProofSerializer)
    def get_delivery_proof(self, obj):
        serializer_context = {'wallet_id': self.context.get('wallet_id')}
        serializer = DeliveryProofSerializer(
            obj, read_only=True, context=serializer_context)

        # if dictionary is empty return None
        if serializer.data:
            return serializer.data
        else:
            return None

    class Meta:
        model = Transfer
        swagger_schema_fields = {
            'title': 'Transaction'
        }
        fields = (
            'id',
            'tx_id',
            'amount',
            'amount_swapped',
            'wallet',
            'recipient',
            'nonce',
            'passive',
            'position',
            'sender_active_state',
            'recipient_active_state',
            'recipient_fulfillment_active_state',
            'recipient_finalization_active_state',
            'swap_freezing_signature',
            'sender_cancellation_active_state',
            'sender_finalization_active_state',
            'recipient_cancellation_active_state',
            'sender_starting_balance',
            'recipient_starting_balance',
            'delivery_proof',
            'eon_number',
            'processed',
            'complete',
            'voided',
            'cancelled',
            'appended',
            'swap',
            'sell_order',
            'matched_amounts',
            'time')
        read_only_fields = fields


class ConciseTransactionSerializer(serializers.ModelSerializer):
    wallet = WalletSerializer(
        read_only=True)
    recipient = WalletSerializer(
        read_only=True)
    time = serializers.IntegerField(source='get_timestamp', read_only=True)

    class Meta:
        model = Transfer
        fields = (
            'id',
            'tx_id',
            'amount',
            'amount_swapped',
            'wallet',
            'recipient',
            'nonce',
            'passive',
            'eon_number',
            'complete',
            'voided',
            'swap',
            'cancelled',
            'time')

        read_only_fields = fields

    def to_representation(self, instance):
        return {
            "wallet": {
                "address": add_0x_prefix(instance.wallet.address),
                "token": add_0x_prefix(instance.wallet.token.address)
            },
            "recipient": {
                "address": add_0x_prefix(instance.recipient.address),
                "token": add_0x_prefix(instance.recipient.token.address)
            },
            "time": instance.get_timestamp(),
            "id": instance.id,
            "tx_id": instance.tx_id,
            "eon_number": instance.eon_number,
            "swap": instance.swap,
            "passive": instance.passive,
            "complete": instance.complete,
            "cancelled": instance.cancelled,
            "voided": instance.voided,
            "nonce": str(instance.nonce),
            "amount": str(instance.amount),
            "amount_swapped": str(instance.amount_swapped),
        }
