from rest_framework import serializers


class MinimumAvailableBalanceMarkerSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return {
            'available': int(instance.amount)
        }
