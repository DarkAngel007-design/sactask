from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import filter_products
from .models import Product
from .pagination import ProductPagination
from .serializers import ProductSerializer, PurchaseSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    lookup_value_regex = r'[0-9]+'

    def get_queryset(self):
        return filter_products(super().get_queryset(), self.request.query_params)

    @action(detail=True, methods=['post'])
    def purchase(self, request, pk=None):
        serializer = PurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data['quantity']

        with transaction.atomic():
            # Lock the row so two purchases at the same time cannot oversell.
            product = get_object_or_404(Product.objects.select_for_update(), pk=pk)

            if quantity > product.stock:
                return Response(
                    {
                        'detail': f'Insufficient stock: requested {quantity}, '
                                  f'only {product.stock} available.',
                        'available_stock': product.stock,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product.stock -= quantity
            product.save(update_fields=['stock', 'updated_at'])

        return Response({
            'id': product.id,
            'name': product.name,
            'quantity_purchased': quantity,
            'remaining_stock': product.stock,
            'total_price': str(product.price * quantity),
        })
