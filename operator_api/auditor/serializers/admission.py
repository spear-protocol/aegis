from rest_framework import serializers
from ledger.models import Wallet


class AdmissionSerializer(serializers.Serializer):
    eon_number = serializers.IntegerField(min_value=0, read_only=True)
    authorization = serializers.CharField(max_length=130, read_only=True)
    operator_authorization = serializers.CharField(
        max_length=130, read_only=True)
    trail_identifier = serializers.IntegerField(min_value=0, read_only=True)

    class Meta:
        swagger_schema_fields = {
            'title': 'Admission'
        }

    def to_representation(self, instance: Wallet):
        return {
            'eon_number':
                instance.registration_eon_number,
            'authorization':
                instance.registration_authorization.value if instance.registration_authorization else None,
            'operator_authorization':
                instance.registration_operator_authorization.value if instance.registration_operator_authorization else None,
            'trail_identifier':
                instance.trail_identifier,
        }
