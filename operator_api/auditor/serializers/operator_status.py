from rest_framework import serializers


class BlockDataSerializer(serializers.Serializer):
    block = serializers.IntegerField(min_value=0, read_only=True)
    eon_number = serializers.IntegerField(min_value=0, read_only=True)

    class Meta:
        ref_name = None


class OperatorStatusSerializer(serializers.Serializer):
    latest = BlockDataSerializer(read_only=True)
    confirmed = BlockDataSerializer(read_only=True)
    blocks_per_eon = serializers.IntegerField(min_value=0, read_only=True)
    confirmation_blocks = serializers.IntegerField(min_value=0, read_only=True)
