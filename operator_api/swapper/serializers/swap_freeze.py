from rest_framework import serializers
from django.db import transaction
from operator_api import crypto
from ledger.models import Transfer, Signature
from ledger.serializers import SignatureSerializer
from contractor.interfaces import LocalViewInterface
from operator_api.models import ErrorCode
from auditor.serializers import SwapMatchedAmountSerializer


class SwapFreezeSerializer(serializers.ModelSerializer):
    freezing_signature = SignatureSerializer(write_only=True)
    matched_amounts = SwapMatchedAmountSerializer(
        source='*',
        read_only=True)

    class Meta:
        model = Transfer
        fields = ('id', 'tx_id', 'freezing_signature', 'matched_amounts')
        read_only_fields = ('id', 'tx_id', 'matched_amounts',)
        error_codes = [
            ErrorCode.SWAP_ALREADY_FULFILLED,
            ErrorCode.SWAP_ALREADY_FROZEN,
            ErrorCode.SWAP_ALREADY_VOIDED,
            ErrorCode.SWAP_ALREADY_CLOSED,
            ErrorCode.INVALID_FREEZING_SIGNATURE,
        ]

    def update(self, swap, validated_data):
        with transaction.atomic():
            current_eon = LocalViewInterface.latest().eon_number()
            swap_set = Transfer.objects.select_for_update().filter(
                tx_id=swap.tx_id, eon_number__gte=current_eon, swap=True).order_by('eon_number')

            current_swap = swap_set[0]

            if current_swap.complete:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_FULFILLED)
            elif current_swap.cancelled:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_FROZEN)
            elif current_swap.voided:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_VOIDED)
            elif current_swap.processed:
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.SWAP_ALREADY_CLOSED)

            freezing_signature_data = validated_data.pop('freezing_signature')
            freezing_checksum = crypto.hex_value(
                current_swap.swap_cancellation_message_checksum())
            freezing_signature = Signature(
                wallet=current_swap.wallet,
                checksum=freezing_checksum,
                value=freezing_signature_data.get('value'))

            if not freezing_signature.is_valid():
                raise serializers.ValidationError(
                    detail='', code=ErrorCode.INVALID_FREEZING_SIGNATURE)
            freezing_signature.save()

            # only current swap should be locked, future swaps are not matched
            with current_swap.lock(auto_renewal=False), current_swap.wallet.lock(auto_renewal=False), current_swap.recipient.lock(auto_renewal=False):
                swap_set.update(cancelled=True,
                                swap_freezing_signature=freezing_signature)
        return current_swap
