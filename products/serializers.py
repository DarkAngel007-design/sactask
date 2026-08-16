from rest_framework import serializers

from .models import Order, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Name cannot be blank.')
        return value


class PurchaseSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    remaining_stock = serializers.IntegerField(source='product.stock', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'product', 'product_name', 'quantity', 'unit_price',
                  'total_price', 'remaining_stock', 'created_at']
        read_only_fields = fields
