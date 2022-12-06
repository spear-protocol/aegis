from datetime import datetime, timezone
from django.conf import settings
from rest_framework.response import Response
from eth_utils import remove_0x_prefix
from rest_framework import generics
from django.shortcuts import get_object_or_404
from .models import Agreement
from .serializers import SLASubscriptionSerializer, SLASerializer
from operator_api.models import MockModel
from drf_yasg.utils import swagger_auto_schema
from django.utils.decorators import method_decorator
from datetime import datetime, timedelta, timezone


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve a wallet's SLA status.",
))
@method_decorator(name='post', decorator=swagger_auto_schema(
    operation_description="Subscribe to SLA (payment should be made prior to this call, payment id is then used to register).",
))
class SLAView(generics.GenericAPIView):
    serializer_class = SLASubscriptionSerializer

    def get(self, request, *args, **kwargs):
        wallet_address = remove_0x_prefix(kwargs.get('wallet'))

        now = datetime.now(tz=timezone.utc)

        agreement = get_object_or_404(
            Agreement,
            wallet__address__iexact=wallet_address,
            expiry__gt=now)

        return Response(
            status=200,
            data=SLASubscriptionSerializer(agreement).data)

    def post(self, request, *args, **kwargs):
        serializer = SLASubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        transfer = validated_data.pop('transfer')

        now = datetime.now(tz=timezone.utc)
        expiry = now + timedelta(days=settings.SLA_DURATION)

        agreement = Agreement.objects.create(
            wallet=transfer.wallet,
            transfer=transfer,
            beginning=now,
            expiry=expiry)

        return Response(
            status=201,
            data=SLASubscriptionSerializer(agreement).data)


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve SLA information.",
))
class SLATokenView(generics.GenericAPIView):
    serializer_class = SLASerializer

    def get(self, request, *args, **kwargs):
        data_model = MockModel(token=settings.SLA_TOKEN_ADDRESS, cost=settings.SLA_PRICE,
                               recipient=settings.SLA_RECIPIENT_ADDRESS, limit=settings.SLA_THRESHOLD)
        return Response(
            status=200,
            data=SLASerializer(data_model).data
        )
