from rest_framework import serializers
from .models import Vehicle, VehicleType, DriverEarning


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'type', 'description']


class VehicleSerializer(serializers.ModelSerializer):
    vehicle_type = VehicleTypeSerializer(source='vehicle_type_id', read_only=True)
    vehicle_type_id_val = serializers.IntegerField(
        source='vehicle_type_id.id', read_only=True
    )

    class Meta:
        model = Vehicle
        fields = [
            'id', 'vehicle_number', 'brand', 'model', 'color', 'year',
            'capacity', 'vehicle_pic', 'rc_doc', 'status',
            'vehicle_type', 'vehicle_type_id_val',
        ]
        read_only_fields = ['id', 'status']


class VehicleCreateSerializer(serializers.Serializer):
    vehicle_number = serializers.CharField(max_length=20)
    vehicle_type = serializers.CharField(max_length=50)
    brand = serializers.CharField(max_length=100, required=False, default='')
    model = serializers.CharField(max_length=100, required=False, default='')
    color = serializers.CharField(max_length=50, required=False, default='')
    year = serializers.IntegerField(required=False, default=None)
    capacity = serializers.IntegerField(required=False, default=1)

    def validate_vehicle_type(self, value):
        try:
            VehicleType.objects.get(type=value)
        except VehicleType.DoesNotExist:
            raise serializers.ValidationError(
                f"Vehicle type '{value}' not found. Available: "
                f"{list(VehicleType.objects.values_list('type', flat=True))}"
            )
        return value


class DriverEarningSerializer(serializers.ModelSerializer):
    trip_id_val = serializers.IntegerField(source='trip_id.id', read_only=True)

    class Meta:
        model = DriverEarning
        fields = ['id', 'trip_id_val', 'commission', 'net_amount']
