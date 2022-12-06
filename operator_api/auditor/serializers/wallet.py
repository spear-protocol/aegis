from eth_utils import remove_0x_prefix, add_0x_prefix
from rest_framework import serializers

from ledger.models import Wallet, Token
from operator_api.models import ErrorCode


class WalletSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=42)
    token = serializers.CharField(max_length=42)
    trail_identifier = serializers.IntegerField(read_only=True)

    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError(
                detail='A valid dictionary is required.')

        try:
            token = Token.objects.get(
                address=remove_0x_prefix(data.get('token')))
        except Token.DoesNotExist:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.TOKEN_NOT_REGISTERED)

        try:
            return Wallet.objects.get(address=remove_0x_prefix(data.get('address')), token=token)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.WALLET_NOT_ADMITTED)

    def to_representation(self, instance):
        return {
            'address': add_0x_prefix(instance.address),
            'token': add_0x_prefix(instance.token.address),
            'trail_identifier': instance.trail_identifier
        }
