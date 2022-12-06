from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from eth_utils import add_0x_prefix
from rest_framework import generics, viewsets, pagination
from rest_framework.response import Response
from auditor.serializers import WalletStateSerializer, AdmissionSerializer, TokenSerializer, TransactionSerializer, OrderMatchSerializer, ConciseTransactionSerializer, OperatorStatusSerializer
from auditor.serializers.orderbook import OrderBookSerializer
from auditor.util import SwapDataRequest
from contractor.interfaces import LocalViewInterface
from operator_api.crypto import remove_0x_prefix
from operator_api.models import MockModel
from ledger.models import Wallet, Token, Transfer, Matching
from datetime import datetime
from django.utils import timezone
from django.db.models import Q
from .permissions import IpWhitelistPermission
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.utils.decorators import method_decorator
from django.conf import settings
from .tasks import cache_wallet_data


class StandardLimitPagination(pagination.LimitOffsetPagination):
    default_limit = 10
    max_limit = 50


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve operator information.",
))
class OperatorStatusView(generics.GenericAPIView):
    serializer_class = OperatorStatusSerializer

    def get(self, request, *args, **kwargs):
        latest = LocalViewInterface.latest()
        confirmed = LocalViewInterface.confirmed()

        data_model = MockModel(
            latest=MockModel(block=latest.block,
                             eon_number=latest.eon_number()),
            confirmed=MockModel(block=confirmed.block,
                                eon_number=confirmed.eon_number()),
            blocks_per_eon=LocalViewInterface.get_contract_parameters().blocks_per_eon,
            confirmation_blocks=settings.HUB_LQD_CONTRACT_CONFIRMATIONS
        )

        return Response(
            status=200,
            data=OperatorStatusSerializer(data_model).data
        )


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="List all tokens supported by the operator.",
))
class TokenListView(generics.ListAPIView):
    serializer_class = TokenSerializer
    queryset = Token.objects.all()


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve order book for a given token pair.",
    manual_parameters=[
        openapi.Parameter('left_token', openapi.IN_PATH,
                          description="First token address of the pair.", type=openapi.TYPE_STRING),
        openapi.Parameter('right_token', openapi.IN_PATH,
                          description="Second token address of the pair.", type=openapi.TYPE_STRING),
        openapi.Parameter('eon_number', openapi.IN_QUERY,
                          description="Retrieve orderbook of a specific eon_number (omitting this parameter will fetch current eon's orderbook by default).", type=openapi.TYPE_INTEGER),
    ]
))
class SwapListView(generics.GenericAPIView):
    serializer_class = OrderBookSerializer

    def get(self, request, *args, **kwargs):
        left_token_address = remove_0x_prefix(kwargs.get('left_token'))
        right_token_address = remove_0x_prefix(kwargs.get('right_token'))
        eon_number = request.query_params.get('eon_number')

        swap_data_request = SwapDataRequest(
            left_token=get_object_or_404(
                Token, address__iexact=left_token_address),
            right_token=get_object_or_404(
                Token, address__iexact=right_token_address),
            eon_number=eon_number)

        return Response(
            status=200,
            data=OrderBookSerializer(swap_data_request).data)


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve all wallet state data.",
    manual_parameters=[
        openapi.Parameter('eon_number', openapi.IN_PATH,
                          description="Fetch state for this specific eon_number.", type=openapi.TYPE_INTEGER),
        openapi.Parameter('token', openapi.IN_PATH,
                          description="Token address of a wallet.", type=openapi.TYPE_STRING),
        openapi.Parameter('wallet', openapi.IN_PATH,
                          description="Address of a wallet.", type=openapi.TYPE_STRING),
        openapi.Parameter('transfer_id', openapi.IN_QUERY,
                          description="Filter transfer data by transfer id, fetch data for transfers for ids >= transfer_id (omitting this parameter will fetch everything, slowing things down).", type=openapi.TYPE_INTEGER),
    ]
))
class WalletDataView(generics.GenericAPIView):
    serializer_class = WalletStateSerializer

    def get(self, request, *args, **kwargs):
        eon_number = int(remove_0x_prefix(kwargs.get('eon_number')))
        token_address = remove_0x_prefix(kwargs.get('token'))
        wallet_address = remove_0x_prefix(kwargs.get('wallet'))
        transfer_id = int(request.query_params.get('transfer_id', 0))

        wallet = get_object_or_404(
            Wallet,
            address__iexact=wallet_address,
            token__address__iexact=token_address
        )

        request_model = MockModel(
            eon_number=eon_number,
            wallet=wallet,
            transfer_id=transfer_id)

        data = WalletStateSerializer(request_model).data

        cache_wallet_data.delay(
            eon_number,
            kwargs.get('token'),
            kwargs.get('wallet'),
            data
        )

        return Response(
            status=200,
            data=data)


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve wallet admission data.",
    manual_parameters=[
        openapi.Parameter('token', openapi.IN_PATH,
                          description="Token address of a wallet.", type=openapi.TYPE_STRING),
        openapi.Parameter('wallet', openapi.IN_PATH,
                          description="Address of a wallet.", type=openapi.TYPE_STRING),
    ]
))
class WalletIdentifierView(generics.GenericAPIView):
    serializer_class = AdmissionSerializer

    def get(self, request, *args, **kwargs):
        wallet = get_object_or_404(
            Wallet,
            address__iexact=remove_0x_prefix(kwargs.get('wallet')),
            token__address__iexact=remove_0x_prefix(kwargs.get('token')))

        return Response(
            status=200,
            data=AdmissionSerializer(wallet, read_only=True).data)


@method_decorator(name='retrieve', decorator=swagger_auto_schema(
    operation_description="Retrieve full details of a specific transaction.",
))
class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transfer.objects.all()
    serializer_class = TransactionSerializer


@method_decorator(name='list', decorator=swagger_auto_schema(
    operation_description="List transactions, returns a concise form of transaction data.",
    manual_parameters=[
        openapi.Parameter('ordering', openapi.IN_QUERY,
                          description="Which field to use when ordering the results (eg. 'time' for ascending order or '-time' for descending).", type=openapi.TYPE_STRING),
        openapi.Parameter('tx_id', openapi.IN_QUERY,
                          description="Filter by a UUID that correlates multi-eon swaps, this field is unique for regular transfers.", type=openapi.TYPE_STRING),
        openapi.Parameter('eon_number', openapi.IN_QUERY,
                          description="Filter by eon_number, when the transaction is active.", type=openapi.TYPE_INTEGER),
        openapi.Parameter('nonce', openapi.IN_QUERY,
                          description="Filter by transaction's nonce.", type=openapi.TYPE_INTEGER),
        openapi.Parameter('passive', openapi.IN_QUERY,
                          description="If set will only fetch passive transfers.", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('swap', openapi.IN_QUERY,
                          description="If set will only fetch swaps.", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('complete', openapi.IN_QUERY,
                          description="If set will only fetch fulfilled swaps and confirmed transfers.", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('cancelled', openapi.IN_QUERY,
                          description="If set will only fetch cancelled swaps.", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('voided', openapi.IN_QUERY,
                          description="If set will only fetch voides transactions, transactions are voided if their state is invalid (eg. trying to overspend).", type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('search', openapi.IN_QUERY,
                          description="Filter transactions by substring of sender/recipient address or token address (excluding 0x prefix).", type=openapi.TYPE_STRING),
    ]
))
class ConciseTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transfer.objects.all() \
        .select_related('wallet').select_related('recipient') \
        .select_related('wallet__token').select_related('recipient__token')

    serializer_class = ConciseTransactionSerializer
    pagination_class = StandardLimitPagination
    filter_backends = (filters.OrderingFilter,
                       DjangoFilterBackend, filters.SearchFilter)
    filter_fields = ('tx_id', 'eon_number', 'nonce', 'passive',
                     'swap', 'complete', 'cancelled', 'voided')
    search_fields = ('wallet__token__address', 'wallet__address',
                     'recipient__token__address', 'recipient__address')


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve token pair matching data, this endpoint is accessed only via IP whitelisting (if query parameters are omitted today's data is fetched).",
    manual_parameters=[
        openapi.Parameter('left_token', openapi.IN_PATH,
                          description="First token address of the pair.", type=openapi.TYPE_STRING),
        openapi.Parameter('right_token', openapi.IN_PATH,
                          description="Second token address of the pair.", type=openapi.TYPE_STRING),
        openapi.Parameter('start_time', openapi.IN_QUERY,
                          description="Fetch only data since timestamp -inclusive-, by default it's today.", type=openapi.TYPE_INTEGER),
        openapi.Parameter('end_time', openapi.IN_QUERY,
                          description="Fetch only data till timestamp -inclusive-, by default it's today.", type=openapi.TYPE_INTEGER),
    ]
))
class MatchingPriceListView(generics.GenericAPIView):
    serializer_class = OrderMatchSerializer
    queryset = ''

    def get(self, request, *args, **kwargs):
        left_token_address = remove_0x_prefix(kwargs.get('left_token'))
        right_token_address = remove_0x_prefix(kwargs.get('right_token'))

        left_token = get_object_or_404(
            Token, address__iexact=left_token_address)
        right_token = get_object_or_404(
            Token, address__iexact=right_token_address)

        start_time = self.request.query_params.get('start_time')
        end_time = self.request.query_params.get('end_time')

        if start_time is None:
            # yesterday
            start_time = timezone.now()
        else:
            try:
                start_time = timezone.make_aware(datetime.fromtimestamp(
                    int(start_time)))
            except ValueError as err:
                return Response(status=400, data="Wrong query parameter format, {}".format(err))

        if end_time is None:
            # tomorrow
            end_time = timezone.now()
        else:
            try:
                print(int(end_time))
                end_time = timezone.make_aware(datetime.fromtimestamp(
                    int(end_time)))
            except ValueError as err:
                return Response(status=400, data="Wrong query parameter format, {}".format(err))

        # time range query should be inclusive (postgres range default is inclusive)
        matches = Matching.objects.filter(
            Q(
                left_token=left_token,
                right_token=right_token
            ) |
            Q(
                left_token=right_token,
                right_token=left_token
            ),
            # range is non-inclusive, so this will fetch today's matches by default
            creation_time__range=[start_time, end_time]
        )

        return Response(
            status=200,
            data=OrderMatchSerializer(matches, many=True, context={'left_token': left_token}).data)
