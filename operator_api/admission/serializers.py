from eth_utils import remove_0x_prefix, add_0x_prefix
from rest_framework import serializers
from ledger.models import Wallet, Signature, BlacklistEntry, Token
from ledger.serializers import SignatureSerializer
from operator_api.crypto import hex_value
from contractor.interfaces import LocalViewInterface
from django.db import transaction
from django.conf import settings
from operator_api.models import ErrorCode
from tos.models import TOSConfig, TOSSignature


class AdmissionRequest(serializers.Serializer):
    authorization = SignatureSerializer(write_only=True)
    token = serializers.CharField(
        max_length=42)
    address = serializers.CharField(
        max_length=42)
    tos_signature = SignatureSerializer(write_only=True)

    class Meta:
        ref_name = None

    def to_representation(self, wallet):
        return {
            'authorization': None,
            'address': add_0x_prefix(wallet.address),
            'token': add_0x_prefix(wallet.token.address),
            'tos_signature': None,
        }


class AdmissionRequestSerializer(AdmissionRequest):
    class Meta:
        error_codes = [
            ErrorCode.TOKEN_NOT_REGISTERED,
            ErrorCode.WALLET_BLACKLISTED,
            ErrorCode.WALLET_ALREADY_ADMITTED,
            ErrorCode.INVALID_ADMISSION_SIGNATURE,
            ErrorCode.INVALID_TOS_SIGNATURE,
        ]

    def validate_token(self, value):
        try:
            token = Token.objects.get(address__iexact=value)
        except Token.DoesNotExist:
            raise serializers.ValidationError(
                detail='', code=ErrorCode.TOKEN_NOT_REGISTERED)
        return token

    def validate(self, attrs):
        authorization = attrs.pop('authorization').get('value')
        address = attrs.get('address')
        token = attrs.get('token')
        tos_signature = attrs.pop('tos_signature').get('value')

        if BlacklistEntry.objects.filter(address__iexact=remove_0x_prefix(address)).exists():
            raise serializers.ValidationError(
                detail='', code=ErrorCode.WALLET_BLACKLISTED)

        if Wallet.objects.filter(address__iexact=remove_0x_prefix(address), token=token).exists():
            raise serializers.ValidationError(
                detail='', code=ErrorCode.WALLET_ALREADY_ADMITTED)

        dummy_wallet = Wallet(
            token=token,
            address=remove_0x_prefix(address))

        attrs['registration_eon_number'] = LocalViewInterface.latest().eon_number()
        admission_hash = hex_value(dummy_wallet.get_admission_hash(
            attrs['registration_eon_number']))

        attrs['signature'] = Signature(
            wallet=dummy_wallet,
            checksum=admission_hash,
            value=authorization)

        if not attrs['signature'].is_valid():
            raise serializers.ValidationError(
                detail='', code=ErrorCode.INVALID_ADMISSION_SIGNATURE)

        latest_tos_config = TOSConfig.objects.all().order_by('time').last()

        attrs['tos_signature'] = Signature(
            wallet=dummy_wallet,
            checksum=latest_tos_config.digest(),
            value=tos_signature)

        if not attrs['tos_signature'].is_valid():
            raise serializers.ValidationError(
                detail='Invalid TOS (digest: {}) signature'.format(latest_tos_config.digest()), code=ErrorCode.INVALID_TOS_SIGNATURE)

        attrs['tos_config'] = latest_tos_config

        return attrs

    def create(self, validated_data):
        signature = validated_data.get('signature')
        tos_signature = validated_data.get('tos_signature')
        tos_config = validated_data.get('tos_config')

        wallet = Wallet(
            token=validated_data.get('token'),
            address=validated_data.get('address'),
            registration_eon_number=validated_data.get('registration_eon_number'))

        with transaction.atomic():
            wallet.save()

            signature.wallet = wallet
            signature.save()

            wallet.registration_authorization = signature
            wallet.save()

            if not TOSSignature.objects.filter(address=wallet.address, tos_config=tos_config).exists():
                tos_signature.wallet = wallet
                tos_signature.save()
                TOSSignature.objects.get_or_create(
                    address=wallet.address,
                    tos_config=tos_config,
                    defaults={'tos_signature': tos_signature},
                )

        return wallet


class AdmissionRequestsSerializer(serializers.Serializer):
    admissions = AdmissionRequest(many=True)

    class Meta:
        error_codes = [
            ErrorCode.TOO_MANY_ADMISSION_REQUESTS,
            ErrorCode.TOKEN_NOT_REGISTERED,
            ErrorCode.INVALID_ADMISSION_SIGNATURE,
            ErrorCode.INVALID_TOS_SIGNATURE,
        ]

    def validate(self, attrs):
        admission_requests = attrs.pop('admissions')

        if len(admission_requests) > settings.BULK_ADMISSION_LIMIT:
            raise serializers.ValidationError(detail='Expected <= {} but got {} admisson requests.'.format(
                settings.BULK_ADMISSION_LIMIT, len(admission_requests)), code=ErrorCode.TOO_MANY_ADMISSION_REQUESTS)

        registration_eon_number = LocalViewInterface.latest().eon_number()
        latest_tos_config = TOSConfig.objects.all().order_by('time').last()

        attrs['signatures'] = []
        attrs['tos_signatures'] = []
        attrs['wallets'] = []

        all_tokens = {}
        for token in Token.objects.all():
            all_tokens[token.address.lower()] = token

        for admission_request in admission_requests:
            address = remove_0x_prefix(admission_request['address'])
            token = all_tokens.get(remove_0x_prefix(
                admission_request['token']).lower())

            if token is None:
                raise serializers.ValidationError(detail='This token {} is not registered.'.format(
                    admission_request['token']), code=ErrorCode.TOKEN_NOT_REGISTERED)

            if BlacklistEntry.objects.filter(address__iexact=address).exists():
                continue

            if Wallet.objects.filter(address__iexact=address, token=token).exists():
                continue

            wallet = Wallet(
                token=token,
                address=address,
                registration_eon_number=registration_eon_number)

            admission_hash = hex_value(
                wallet.get_admission_hash(registration_eon_number))

            signature = Signature(
                wallet=wallet,
                checksum=admission_hash,
                value=admission_request.get('authorization').get('value'))

            if not signature.is_valid():
                raise serializers.ValidationError(detail='Invalid authorization for address {} and token {}.'.format(
                    admission_request['address'], admission_request['token']), code=ErrorCode.INVALID_ADMISSION_SIGNATURE)

            tos_signature = Signature(
                wallet=wallet,
                checksum=latest_tos_config.digest(),
                value=admission_request.get('tos_signature').get('value'))

            if not tos_signature.is_valid():
                raise serializers.ValidationError(detail='Invalid TOS (digest: {}) signature for address {} and token {}.'.format(
                    latest_tos_config.digest(), admission_request['address'], admission_request['token']), code=ErrorCode.INVALID_TOS_SIGNATURE)

            attrs['signatures'].append(signature)
            attrs['tos_signatures'].append(tos_signature)
            attrs['wallets'].append(wallet)

        attrs['tos_config'] = latest_tos_config
        return attrs

    def to_representation(self, wallets):
        return {
            'admissions': AdmissionRequest(wallets, many=True).data
        }
