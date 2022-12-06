from rest_framework import serializers
from ledger.models import Transfer


class SwapMatchedAmountSerializer(serializers.Serializer):
    matched_in = serializers.DecimalField(
        read_only=True, min_value=0, max_digits=80, decimal_places=0)
    matched_out = serializers.DecimalField(
        read_only=True, min_value=0, max_digits=80, decimal_places=0)

    class Meta:
        swagger_schema_fields = {
            'title': 'MatchedAmount'
        }

    def to_representation(self, transfer: Transfer):
        if not transfer.is_swap():
            return None

        matched_out, matched_in = transfer.matched_amounts(all_eons=True)

        return {
            'matched_in': str(matched_in),
            'matched_out': str(matched_out)
        }
