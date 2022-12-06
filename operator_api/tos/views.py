from .serializers import TOSSignatureSerializer, TOSConfigSerializer
from .models import TOSSignature, TOSConfig
from rest_framework import generics, status
from django.db import transaction
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema


@method_decorator(name='get', decorator=swagger_auto_schema(
    operation_description="Retrieve operator's latest terms of service and privacy digest."
))
class TOSConfigView(generics.RetrieveAPIView):
    serializer_class = TOSConfigSerializer
    queryset = TOSConfig.objects.all()

    def get_object(self):
        return self.get_queryset().order_by('time').last()


@method_decorator(name='post', decorator=swagger_auto_schema(
    operation_description="Submit a new signature of the latest terms of service."
))
class TOSSignatureView(generics.GenericAPIView):
    serializer_class = TOSSignatureSerializer

    def post(self, request, format=None):
        serializer = TOSSignatureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        tos_signature = validated_data.get('tos_signature')
        tos_config = validated_data.get('tos_config')
        address = validated_data.get('address')

        with transaction.atomic():
            tos_signature.save()

            tos_signature_config = TOSSignature(
                address=address,
                tos_config=tos_config,
                tos_signature=tos_signature
            )

            tos_signature_config.save()

        return Response(TOSSignatureSerializer(tos_signature_config).data, status=status.HTTP_201_CREATED)
