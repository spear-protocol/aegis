from rest_framework import serializers
from ledger.models import Matching
from eth_utils import add_0x_prefix


class OrderMatchSerializer(serializers.Serializer):
    volume = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    price = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    time = serializers.IntegerField(min_value=0, read_only=True)

    def to_representation(self, instance):

        left_token = self.context.get('left_token')

        if left_token == instance.left_token:
            price = int(instance.right_deducted_left_granted_amount /
                        instance.left_deducted_right_granted_amount * 10000) / 10000
            volume = instance.left_deducted_right_granted_amount
        else:
            price = int(instance.left_deducted_right_granted_amount /
                        instance.right_deducted_left_granted_amount * 10000) / 10000
            volume = instance.right_deducted_left_granted_amount

        return {
            'volume': str(volume),
            'price': str(price),
            'time': instance.get_timestamp(),
        }
