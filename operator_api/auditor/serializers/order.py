from rest_framework import serializers


class OrderSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    amount_swapped = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    remaining_out = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)
    remaining_in = serializers.DecimalField(
        min_value=0, max_digits=80, decimal_places=0, read_only=True)

    def to_representation(self, instance):
        if instance is None:
            return None

        return {
            'amount': str(instance.get('amount')),
            'amount_swapped': str(instance.get('amount_swapped')),
            'remaining_out': str(instance.get('remaining_out')),
            'remaining_in': str(instance.get('remaining_in')),
        }
