from drf_spectacular.utils import OpenApiExample, OpenApiResponse
from rest_framework import serializers


class ErrorDetailSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.DictField()


ERROR_RESPONSE = OpenApiResponse(
    response=ErrorDetailSerializer,
    description="Erreur API standardisée.",
    examples=[
        OpenApiExample(
            "Erreur métier",
            value={
                "error": {
                    "code": "STEP_UP_REQUIRED",
                    "message": "Verification renforcee requise.",
                    "details": {},
                }
            },
        )
    ],
)
