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
    """CRUD for products, plus a purchase action.

    ModelViewSet gives us, via the router in urls.py:
        GET    /api/products/          list   (paginated, searchable, filterable)
        POST   /api/products/          create
        GET    /api/products/{id}/     retrieve
        PUT    /api/products/{id}/     update       (full replace)
        PATCH  /api/products/{id}/     partial_update
        DELETE /api/products/{id}/     destroy
    and we add:
        POST   /api/products/{id}/purchase/
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = ProductPagination

    # Only numeric ids match the URL, so /api/products/abc/ is a clean 404
    # instead of a 500 caused by comparing 'abc' to an integer column.
    lookup_value_regex = r'[0-9]+'

    def get_queryset(self):
        """The list endpoint's queryset, narrowed by the query parameters."""
        return filter_products(super().get_queryset(), self.request.query_params)

    @action(detail=True, methods=['post'])
    def purchase(self, request, pk=None):
        """Buy `quantity` units of this product and decrement its stock."""
        serializer = PurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # -> HTTP 400 on bad input
        quantity = serializer.validated_data['quantity']

        with transaction.atomic():
            # select_for_update() locks this row until the transaction commits,
            # so two purchases arriving at the same moment cannot both read the
            # same stock value and oversell. (No-op on SQLite, correct on
            # PostgreSQL/MySQL.)
            product = get_object_or_404(
                Product.objects.select_for_update(), pk=pk
            )

            if quantity > product.stock:
                return Response(
                    {
                        'detail': (
                            f'Insufficient stock: requested {quantity}, '
                            f'only {product.stock} available.'
                        ),
                        'available_stock': product.stock,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product.stock -= quantity
            product.save(update_fields=['stock', 'updated_at'])

        return Response(
            {
                'id': product.id,
                'name': product.name,
                'quantity_purchased': quantity,
                'remaining_stock': product.stock,
                'total_price': str(product.price * quantity),
            },
            status=status.HTTP_200_OK,
        )
