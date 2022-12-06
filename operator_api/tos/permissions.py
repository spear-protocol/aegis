from rest_framework.permissions import BasePermission
from rest_framework.exceptions import APIException
from rest_framework import status, serializers
from django.conf import settings
from django.utils import timezone
from eth_utils import remove_0x_prefix, add_0x_prefix
from .models import TOSSignature, TOSConfig
from ledger.models import Wallet
import datetime
from operator_api.models.errors import ErrorCode


class TOSInvalidException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = {
        'code': ErrorCode.INVALID_TOS_SIGNATURE,
        'message': 'Please update your TOS signature.'
    }


# this permission class is applied to transactor and swapper create and update endpoints
# it makes sure that the wallet's owner signed the latest TOS or is still within grace period TOS_UPDATE_WINDOW_DAYS
class SignedLatestTOS(BasePermission):
    message = ErrorCode.INVALID_TOS_SIGNATURE

    def is_valid_tos_signed(self, address):
        # is owner account
        if remove_0x_prefix(address) == remove_0x_prefix(settings.HUB_OWNER_ACCOUNT_ADDRESS):
            return True

        # get latest TOS object
        latest_tos_config = TOSConfig.objects.all().order_by('time').last()

        # if there is no TOS object then allow the user to enter
        if latest_tos_config is None:
            return True

        # get the latest user TOS signature
        latest_tos_signature = TOSSignature.objects.filter(
            address__iexact=remove_0x_prefix(address)).order_by('tos_config__time').last()

        # if the user never signed TOS deny access
        if latest_tos_signature is None:
            return False

        # if the user already signed latest TOS grant access
        if latest_tos_signature.tos_config == latest_tos_config:
            return True

        # if the user did not sign latest TOS but is still within grace period grant access
        # grace period is over if TOS was updated TOS_UPDATE_WINDOW_DAYS days ago
        if latest_tos_config.time > timezone.now() - datetime.timedelta(days=settings.TOS_UPDATE_WINDOW_DAYS):
            return True

        return False

    def has_permission(self, request, view):
        if not ('wallet' in request.data and 'address' in request.data['wallet']):
            return True

        if self.is_valid_tos_signed(request.data['wallet']['address']):
            return True

        raise TOSInvalidException()
