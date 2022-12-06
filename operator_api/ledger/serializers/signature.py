from rest_framework import serializers
from ledger.models import Signature


class SignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signature
        fields = ('value',)
