from drf_yasg import openapi
from drf_yasg.inspectors.view import SwaggerAutoSchema
from drf_yasg.utils import force_real_str, is_list_view
from rest_framework import exceptions
from rest_framework.settings import api_settings
from rest_framework import status
from operator_api.models import ALL_ERROR_CODES
from tos.permissions import TOSInvalidException


class ErrorResponseAutoSchema(SwaggerAutoSchema):

    # def get_generic_error_schema(self):
    #     return openapi.Schema(
    #         'Generic API Error',
    #         type=openapi.TYPE_OBJECT,
    #         properties={
    #             'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error details'),
    #             'code': openapi.Schema(type=openapi.TYPE_STRING, description='Error code', enum=ALL_ERROR_CODES),
    #         },
    #         required=['detail']
    #     )

    def get_tos_exception_schema(self):
        return openapi.Schema(
            'Invalid TOS',
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING, description='Error details', default=TOSInvalidException.default_detail['message']),
                'code': openapi.Schema(type=openapi.TYPE_STRING, description='Error code', default=TOSInvalidException.default_detail['code'], enum=[TOSInvalidException.default_detail['code']]),
            },
        )

    def get_validation_error_schema(self, error_codes=None):
        error_codes = error_codes or ALL_ERROR_CODES
        return openapi.Schema(
            'Validation Error',
            type=openapi.TYPE_OBJECT,
            properties={
                api_settings.NON_FIELD_ERRORS_KEY: openapi.Schema(
                    description='List of validation errors not related to any field',
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        description='error message and code',
                        properties={
                            'message': openapi.Schema(type=openapi.TYPE_STRING),
                            'code': openapi.Schema(type=openapi.TYPE_STRING, enum=error_codes)
                        }
                    ),
                )
            },
            additional_properties=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description='List of validation errors for specific fields',
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description='error message and code',
                    properties={
                            'message': openapi.Schema(type=openapi.TYPE_STRING),
                            'code': openapi.Schema(type=openapi.TYPE_STRING, enum=error_codes)
                    }
                )
            )
        )

    def get_response_serializers(self):
        responses = super().get_response_serializers()
        definitions = self.components.with_scope(
            openapi.SCHEMA_DEFINITIONS)  # type: openapi.ReferenceResolver

        # definitions.setdefault('GenericError', self.get_generic_error_schema)
        definitions.setdefault(
            'ValidationError', self.get_validation_error_schema)
        definitions.setdefault(
            'TOSInvalidException', self.get_tos_exception_schema)
        # definitions.setdefault('APIException', self.get_generic_error_schema)

        serializer = self.get_request_serializer() or self.get_query_serializer()

        for permission in self.view.permission_classes:
            if permission.__name__ == 'SignedLatestTOS':
                responses.setdefault(TOSInvalidException.status_code, openapi.Response(
                    description='TOS expired or was never signed.',
                    schema=openapi.SchemaRef(
                        definitions, 'TOSInvalidException')
                ))

        if serializer:
            meta = getattr(serializer.__class__, 'Meta', None)
            if meta and 'error_codes' in meta.__dict__:
                responses.setdefault(exceptions.ValidationError.status_code, openapi.Response(
                    description=force_real_str(
                        exceptions.ValidationError.default_detail),
                    schema=self.get_validation_error_schema(
                        error_codes=meta.error_codes)
                ))
            else:
                responses.setdefault(exceptions.ValidationError.status_code, openapi.Response(
                    description=force_real_str(
                        exceptions.ValidationError.default_detail),
                    schema=openapi.SchemaRef(definitions, 'ValidationError')
                ))

        # security = self.get_security()
        # if security is None or len(security) > 0:
        #     # Note: 401 error codes are coerced  into 403 see rest_framework/views.py:433:handle_exception
        #     # This is b/c the API uses token auth which doesn't have WWW-Authenticate header
        #     responses.setdefault(status.HTTP_403_FORBIDDEN, openapi.Response(
        #         description="Authentication credentials were invalid, absent or insufficient.",
        #         schema=openapi.SchemaRef(definitions, 'GenericError')
        #     ))
        # if not is_list_view(self.path, self.method, self.view):
        #     responses.setdefault(exceptions.PermissionDenied.status_code, openapi.Response(
        #         description="Permission denied.",
        #         schema=openapi.SchemaRef(definitions, 'APIException')
        #     ))
        #     responses.setdefault(exceptions.NotFound.status_code, openapi.Response(
        #         description="Object does not exist.",
        #         schema=openapi.SchemaRef(definitions, 'APIException')
        #     ))

        return responses
