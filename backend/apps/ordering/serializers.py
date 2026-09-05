from rest_framework import serializers


class ReservationItemSerializer(serializers.Serializer):
    ticket_category_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class ReservationCreateSerializer(serializers.Serializer):
    items = ReservationItemSerializer(many=True, allow_empty=False)
