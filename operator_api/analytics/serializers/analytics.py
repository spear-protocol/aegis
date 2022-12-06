from rest_framework import serializers


class DaySnapshotSerializer(serializers.Serializer):
    day = serializers.DateTimeField(read_only=True)
    count = serializers.IntegerField(min_value=0, read_only=True)


class EonSnapshotSerializer(serializers.Serializer):
    eon_number = serializers.IntegerField(min_value=0, read_only=True)
    count = serializers.IntegerField(min_value=0, read_only=True)


class WalletStatusSerializer(serializers.Serializer):
    total = serializers.IntegerField(min_value=0, read_only=True)
    eon_number = EonSnapshotSerializer(many=True, read_only=True)


class StandardStatusSerializer(serializers.Serializer):
    total = serializers.IntegerField(min_value=0, read_only=True)
    eon_number = EonSnapshotSerializer(many=True, read_only=True)
    time = DaySnapshotSerializer(many=True, read_only=True)


class ChallengeStatusSerializer(StandardStatusSerializer):
    rebuted = serializers.IntegerField(min_value=0, read_only=True)
