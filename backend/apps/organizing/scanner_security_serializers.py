from rest_framework import serializers


class ScannerSecurityCodeRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=(
            "REVOKE",
            "LEAVE_ACCEPT",
        ),
    )


class ScannerSecurityCodeConfirmSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()

    # Volontairement max_length uniquement :
    # une mauvaise forme compte comme tentative OTP.
    code = serializers.CharField(
        max_length=16,
        trim_whitespace=True,
    )
