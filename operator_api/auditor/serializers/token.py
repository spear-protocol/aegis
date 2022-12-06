from rest_framework import serializers
from ledger.models import Token
from eth_utils import add_0x_prefix


class TokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = (
            'address',
            'name',
            'short_name',
        )
        read_only_fields = fields

    def to_representation(self, instance):
        return {
            'address': add_0x_prefix(instance.address),
            'name': instance.name,
            'short_name': instance.short_name
        }
