from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    """Converts Product objects to/from JSON and validates incoming data.

    Because this is a ModelSerializer, the field rules declared on the model
    (max_length, MinValueValidator on price, PositiveIntegerField on stock)
    are turned into API validation automatically.
    """

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'description',
            'price',
            'stock',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        """Reject names that are empty or only whitespace, and trim the rest."""
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Name cannot be blank.')
        return cleaned


class PurchaseSerializer(serializers.Serializer):
    """Validates the body of POST /api/products/{id}/purchase/.

    A plain Serializer (not a ModelSerializer) because the request body is not
    a Product -- it is just {"quantity": <int>}.
    """

    quantity = serializers.IntegerField(min_value=1)


class PurchaseResponseSerializer(serializers.Serializer):
    """Shape of a successful purchase response (documentation + consistency)."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    quantity_purchased = serializers.IntegerField()
    remaining_stock = serializers.IntegerField()
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2)
