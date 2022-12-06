from rest_framework import permissions
from django.conf import settings


class IpWhitelistPermission(permissions.BasePermission):
    @staticmethod
    def get_client_ip(request):
        cf_connecting_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_connecting_ip is not None:
            return cf_connecting_ip.strip()

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for is not None:
            return x_forwarded_for.split(',')[0].strip()

        remote_address = request.META.get('REMOTE_ADDR')
        if remote_address:
            return remote_address.strip()

        return None

    def has_permission(self, request, view):
        client_ip = self.get_client_ip(request)

        if client_ip is not None and client_ip in settings.MATCHING_IP_WHITELIST:
            return True

        return False
