from rest_framework import generics
from ledger.models import Transfer
from swapper.serializers import SwapSerializer, SwapFreezeSerializer, SwapFinalizationSerializer, \
    SwapCancellationSerializer
from tos.permissions import SignedLatestTOS
from drf_yasg.utils import swagger_auto_schema
from django.utils.decorators import method_decorator


@method_decorator(name='post', decorator=swagger_auto_schema(
    operation_description="Create a swap (by default orders are sell orders, to make buy orders change sell_order to false).",
))
class SwapView(generics.CreateAPIView):
    queryset = Transfer.objects.all()
    serializer_class = SwapSerializer
    permission_classes = (SignedLatestTOS,)


@method_decorator(name='put', decorator=swagger_auto_schema(
    operation_description="Freeze a swap, this step is required before attempting to cancel a swap, \
        freezing makes sure that the client has the latest matching data before signing a cancellation active state.",
))
class FreezeSwapView(generics.UpdateAPIView):
    queryset = Transfer.objects.all()
    serializer_class = SwapFreezeSerializer
    http_method_names = ['put']
    permission_classes = (SignedLatestTOS,)


@method_decorator(name='put', decorator=swagger_auto_schema(
    operation_description="Finalize a swap, this is only applicable to fulfilled swaps (complete flag is set), \
        this step is required to unlock a wallet after a swap is fulfilled (wallet is locked until a pending swap \
        is finalized or the current eon ends).",
))
class FinalizeSwapView(generics.UpdateAPIView):
    queryset = Transfer.objects.all()
    serializer_class = SwapFinalizationSerializer
    http_method_names = ['put']
    permission_classes = (SignedLatestTOS,)


@method_decorator(name='put', decorator=swagger_auto_schema(
    operation_description="Cancel a swap, can only cancel a frozen swap to avoid submitting an invalid state.",
))
class CancelSwapView(generics.UpdateAPIView):
    queryset = Transfer.objects.all()
    serializer_class = SwapCancellationSerializer
    http_method_names = ['put']
    permission_classes = (SignedLatestTOS,)
