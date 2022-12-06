from rest_framework import generics
from rest_framework.decorators import api_view
from ledger.models import Transfer
from operator_api import crypto
from rest_framework.response import Response
from contractor.interfaces import NOCUSTContractInterface
from ledger.context.wallet_transfer import WalletTransferContext
from eth_utils import remove_0x_prefix
from ledger.models import Wallet
from .serializers import TransferSerializer
from drf_yasg.utils import swagger_auto_schema
from django.utils.decorators import method_decorator
from tos.permissions import SignedLatestTOS


@method_decorator(name='post', decorator=swagger_auto_schema(
    operation_description="Create a transfer (active transfers will be deprecated soon, please make sure to set the passive flag).",
))
class TransferView(generics.CreateAPIView):
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    permission_classes = (SignedLatestTOS,)


@method_decorator(name='post', decorator=swagger_auto_schema(
    operation_description="Create a delegated withdrawal.",
))
@api_view(('POST',))
def delegated_withdrawal(request):
    signature = request.POST.get("signature")
    wallet_address = request.POST.get("wallet")
    amount = int(request.POST.get("amount"))
    token = request.POST.get("token")
    expiry = int(request.POST.get("expiry"))

    message = [
        crypto.address(wallet_address),
        crypto.address(token),
        crypto.uint256(amount),
        crypto.uint256(expiry)
    ]
    message = crypto.hash_array(message)

    v, r, s = crypto.decode_signature(signature)
    trust = crypto.verify_message_signature(
        crypto.address(wallet_address), message, (v, r, s))

    if not trust:
        return Response(data="Signature is invalid", status=400)

    wallet = Wallet.objects.filter(address=remove_0x_prefix(
        wallet_address), token__address=token).get()
    nc = NOCUSTContractInterface()

    current_eon = nc.get_current_eon_number()
    wallet_view_context = WalletTransferContext(wallet, None)
    available_amount = wallet_view_context.loosely_available_funds_at_eon(
        current_eon, current_eon, False, False)
    if available_amount < amount:
        return Response(data="Not enough funds", status=400)

    nc.delegated_withdraw(token, wallet_address, amount,
                          expiry, crypto.uint256(r), crypto.uint256(s), v)

    return Response(data="Ok", status=200)
