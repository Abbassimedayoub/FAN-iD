from rest_framework import serializers


class TicketAdmissionScanSerializer(serializers.Serializer):
    token = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=4096,
    )
