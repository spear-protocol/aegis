from rest_framework import serializers
from leveller.models import Agreement
from ledger.models import Transfer
from django.conf import settings
from eth_utils import remove_0x_prefix
from datetime import datetime, timezone, timedelta
from operator_api.models.errors import ErrorCode


class SLASubscriptionSerializer(serializers.ModelSerializer):
    expiry = serializers.IntegerField(source='get_timestamp', read_only=True)
    transfer_id = serializers.IntegerField()

    class Meta:
        model = Agreement
        fields = ('transfer_id', 'expiry', )
        read_only_fields = ('expiry', )

        error_codes = [
            ErrorCode.TRANSFER_DOES_NOT_EXIST,
            ErrorCode.TRANSFER_MADE_TO_WRONG_WALLET,
            ErrorCode.TRANSFER_MADE_WITH_WRONG_TOKEN,
            ErrorCode.SLA_ALREADY_EXISTS_FOR_TRANSFER,
            ErrorCode.SLA_STILL_VALID_FOR_WALLET
        ]

    def validate(self, attrs):
        transfer_id = attrs.get('transfer_id')

        try:
            attrs['transfer'] = Transfer.objects.get(
                swap=False, id=transfer_id)
        except Transfer.DoesNotExist:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.TRANSFER_DOES_NOT_EXIST)

        if attrs['transfer'].recipient.address != remove_0x_prefix(settings.SLA_RECIPIENT_ADDRESS):
            raise serializers.ValidationError(
                detail='', code=ErrorCode.TRANSFER_MADE_TO_WRONG_WALLET)

        if attrs['transfer'].recipient.token.address != remove_0x_prefix(settings.SLA_TOKEN_ADDRESS):
            raise serializers.ValidationError(
                detail='', code=ErrorCode.TRANSFER_MADE_WITH_WRONG_TOKEN)

        if Agreement.objects.filter(transfer=attrs['transfer']).exists():
            raise serializers.ValidationError(
                detail='', code=ErrorCode.SLA_ALREADY_EXISTS_FOR_TRANSFER)

        if attrs['transfer'].wallet.has_valid_sla():
            raise serializers.ValidationError(
                detail='', code=ErrorCode.SLA_STILL_VALID_FOR_WALLET)

        return attrs

    def to_representation(self, obj):
        return {
            'expiry': obj.get_timestamp(),
            'transfer_id': obj.transfer.id
        }


class SLASerializer(serializers.Serializer):
    token = serializers.CharField(max_length=42, read_only=True)
    recipient = serializers.CharField(max_length=42, read_only=True)
    cost = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    limit = serializers.IntegerField(min_value=1, read_only=True)
