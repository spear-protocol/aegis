from rest_framework import generics, views, status
from ledger.models import Wallet
from .serializers import AdmissionRequestSerializer, AdmissionRequestsSerializer
from rest_framework.response import Response
from ledger.models import Wallet, Signature
from django.db import transaction
from auditor.serializers import WalletSerializer
from tos.models import TOSSignature
from django.conf import settings
from eth_utils import remove_0x_prefix
from drf_yasg.utils import swagger_auto_schema
from django.utils.decorators import method_decorator


@method_decorator(name='post', decorator=swagger_auto_schema(
    operation_description="Register a single wallet (registration is required for every address-token pairs).",
))
class WalletView(generics.CreateAPIView):
    queryset = Wallet.objects.all()
    serializer_class = AdmissionRequestSerializer


@method_decorator(name='post', decorator=swagger_auto_schema(
    operation_description="Register a list of wallets.",
))
class BulkWalletView(generics.GenericAPIView):
    serializer_class = AdmissionRequestsSerializer

    def post(self, request, format=None):
        serializer = AdmissionRequestsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        signatures = validated_data.get('signatures')
        tos_signatures = validated_data.get('tos_signatures')
        wallets = validated_data.get('wallets')
        tos_config = validated_data.get('tos_config')

        tos_signed_set = set()

        with transaction.atomic():
            Wallet.objects.bulk_create(wallets)

            for i in range(len(signatures)):
                signatures[i].wallet = wallets[i]
            for i in range(len(tos_signatures)):
                tos_signatures[i].wallet = wallets[i]

            Signature.objects.bulk_create(signatures)

            for i in range(len(wallets)):
                wallets[i].registration_authorization = signatures[i]

            Wallet.objects.bulk_update(wallets, ['registration_authorization'])

            tos_records = []
            for i in range(len(wallets)):
                if wallets[i].address not in tos_signed_set and not TOSSignature.objects.filter(address=wallets[i].address, tos_config=tos_config).exists():
                    tos_records.append(TOSSignature(
                        address=wallets[i].address, tos_config=tos_config, tos_signature=tos_signatures[i]))
                    tos_signed_set.add(wallets[i].address)

            TOSSignature.objects.bulk_create(tos_records)

        return Response(AdmissionRequestsSerializer(wallets).data, status=status.HTTP_201_CREATED)
