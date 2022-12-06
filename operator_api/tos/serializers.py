from rest_framework import serializers
from eth_utils import remove_0x_prefix, add_0x_prefix
from operator_api.crypto import hex_value
from contractor.interfaces import LocalViewInterface
from ledger.models import Wallet, Token, Signature
from operator_api.models.errors import ErrorCode
from django.conf import settings
from .models import TOSConfig, TOSSignature


class TOSConfigSerializer(serializers.ModelSerializer):
    time = serializers.IntegerField(source='get_timestamp', read_only=True)

    class Meta:
        model = TOSConfig
        fields = ('privacy_policy_digest', 'terms_of_service_digest', 'time')
        read_only_fields = ('time', )


class TOSSignatureSerializer(serializers.Serializer):
    address = serializers.CharField(
        max_length=42)
    tos_signature = serializers.CharField(
        max_length=130,
        write_only=True)

    class Meta:
        error_codes = [
            ErrorCode.WALLET_NOT_ADMITTED,
            ErrorCode.LATEST_TOS_ALREADY_SIGNED,
            ErrorCode.INVALID_TOS_SIGNATURE,
        ]

    def to_representation(self, instance):
        return {
            'address': instance.address,
            'tos_signature': None
        }

    def validate(self, attrs):
        address = attrs.get('address')
        tos_signature = attrs.pop('tos_signature')

        latest_tos_config = TOSConfig.objects.all().order_by('time').last()

        if TOSSignature.objects.filter(address__iexact=remove_0x_prefix(address), tos_config=latest_tos_config).exists():
            raise serializers.ValidationError(
                detail='', code=ErrorCode.LATEST_TOS_ALREADY_SIGNED)

        wallet = Wallet.objects.filter(
            address__iexact=remove_0x_prefix(address)).last()

        if wallet is None:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.WALLET_NOT_ADMITTED)

        attrs['tos_signature'] = Signature(
            wallet=wallet,
            checksum=hex_value(latest_tos_config.digest()),
            value=tos_signature)

        if not attrs['tos_signature'].is_valid():
            raise serializers.ValidationError(
                detail='Invalid TOS (digest: {}) privacy polict (digest: {}) signature'.format(
                    latest_tos_config.terms_of_service_digest,
                    latest_tos_config.privacy_policy_digest
                ), code=ErrorCode.INVALID_TOS_SIGNATURE)

        attrs['address'] = wallet.address
        attrs['tos_config'] = latest_tos_config

        return attrs
