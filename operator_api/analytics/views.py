from rest_framework import generics
from rest_framework.response import Response
from django.conf import settings
from django.db.models import Count, Sum

from contractor.interfaces import LocalViewInterface
from ledger.models import Wallet, Transfer, Challenge, Deposit, Withdrawal
from operator_api.models import MockModel
from .serializers import WalletStatusSerializer, StandardStatusSerializer, ChallengeStatusSerializer
from drf_yasg.utils import swagger_auto_schema
from django.utils.decorators import method_decorator


def get_time_series(query):
    time_projected_as_day = query.extra({"day": "date_trunc('day', time)"})
    count_per_day = time_projected_as_day.values(
        'day').order_by('day').annotate(count=Count("id"))
    return count_per_day


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve high-level admission data.",
))
class WalletsView(generics.GenericAPIView):
    serializer_class = WalletStatusSerializer
    queryset = ''

    def get(self, request, *args, **kwargs):
        wlts_total = Wallet.objects.all().count()
        registrations_per_eon = Wallet.objects.extra(
            select={
                'eon_number': 'registration_eon_number'
            }
        ).values('eon_number').annotate(count=Count('address')).order_by('eon_number')

        data_model = MockModel(
            total=wlts_total, eon_number=registrations_per_eon)

        return Response(
            status=200,
            data=WalletStatusSerializer(data_model).data
        )


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve high-level transaction data.",
))
class TransfersView(generics.GenericAPIView):
    serializer_class = StandardStatusSerializer
    queryset = ''

    def get(self, request, *args, **kwargs):
        txs_total = Transfer.objects.all().count()
        txs_per_eon = Transfer.objects.values('eon_number').annotate(
            count=Count('id')).order_by('eon_number')
        txs_per_day = get_time_series(Transfer.objects.filter())

        data_model = MockModel(
            total=txs_total, eon_number=txs_per_eon, time=txs_per_day)

        return Response(
            status=200,
            data=StandardStatusSerializer(data_model).data
        )


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve high-level challenge data.",
))
class ChallengesView(generics.GenericAPIView):
    serializer_class = ChallengeStatusSerializer
    queryset = ''

    def get(self, request, *args, **kwargs):
        chs_total = Challenge.objects.all().count()
        chs_rebuted = Challenge.objects.filter(rebuted=True).count()
        chs_per_eon = Challenge.objects.values('eon_number').annotate(
            count=Count('id')).order_by('eon_number')
        chs_per_day = get_time_series(Challenge.objects.filter())

        data_model = MockModel(
            total=chs_total, rebuted=chs_rebuted, eon_number=chs_per_eon, time=chs_per_day)

        return Response(
            status=200,
            data=ChallengeStatusSerializer(data_model).data
        )


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve high-level deposit data.",
))
class DepositsView(generics.GenericAPIView):
    serializer_class = StandardStatusSerializer
    queryset = ''

    def get(self, request, *args, **kwargs):
        dps_total = Deposit.objects.all().count()
        dps_per_eon = Deposit.objects.values('eon_number').annotate(
            count=Count('id')).order_by('eon_number')
        dps_per_day = get_time_series(Deposit.objects.filter())

        data_model = MockModel(
            total=dps_total, eon_number=dps_per_eon, time=dps_per_day)

        return Response(
            status=200,
            data=StandardStatusSerializer(data_model).data
        )


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve high-level withdrawal data.",
))
class WithdrawalsView(generics.GenericAPIView):
    serializer_class = StandardStatusSerializer
    queryset = ''

    def get(self, request, *args, **kwargs):
        wts_total = Withdrawal.objects.all().count()
        wts_per_eon = Withdrawal.objects.values('eon_number').annotate(
            count=Count('id')).order_by('eon_number')
        wts_per_day = get_time_series(Withdrawal.objects.filter())

        data_model = MockModel(
            total=wts_total, eon_number=wts_per_eon, time=wts_per_day)

        return Response(
            status=200,
            data=StandardStatusSerializer(data_model).data
        )
