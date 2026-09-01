from rest_framework import serializers


class ScannerLeaveDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=(
            "ACCEPT",
            "REJECT",
        ),
    )


class ScannerLeaveAcceptOtpSerializer(
    serializers.Serializer
):
    challenge_id = serializers.UUIDField()
    code = serializers.CharField(
        max_length=16,
        trim_whitespace=True,
    )
