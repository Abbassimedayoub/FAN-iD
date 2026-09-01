from rest_framework import serializers


class ScannerArchiveItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    version = serializers.IntegerField(min_value=0)


class ScannerBulkArchiveSerializer(serializers.Serializer):
    scanners = ScannerArchiveItemSerializer(
        many=True,
        allow_empty=False,
    )

    def validate_scanners(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Vous ne pouvez pas archiver plus de 100 scanners à la fois.")

        ids = [item["id"] for item in value]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Un même scanner ne peut pas être sélectionné plusieurs fois.")

        return value
