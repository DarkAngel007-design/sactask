import logging

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .filters import filter_products
from .models import Order, Product
from .pagination import ProductPagination
from .permissions import ReadOnlyOrAdmin
from .serializers import OrderSerializer, ProductSerializer, PurchaseSerializer
from .throttling import PurchaseRateThrottle

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    lookup_value_regex = r'[0-9]+'

    def get_permissions(self):
        if self.action == 'purchase':
            return [permissions.IsAuthenticated()]
        return [ReadOnlyOrAdmin()]

    def get_queryset(self):
        return filter_products(super().get_queryset(), self.request.query_params)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'Cannot delete a product that has orders.'},
                status=status.HTTP_409_CONFLICT,
            )

    @action(detail=True, methods=['post'], throttle_classes=[PurchaseRateThrottle])
    def purchase(self, request, pk=None):
        serializer = PurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        quantity = serializer.validated_data['quantity']
        idempotency_key = request.headers.get('Idempotency-Key', '')[:64]

        if idempotency_key:
            replay = Order.objects.filter(
                user=request.user, idempotency_key=idempotency_key
            ).first()
            if replay:
                return Response(OrderSerializer(replay).data)

        try:
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

                order = Order.objects.create(
                    product=product,
                    user=request.user,
                    quantity=quantity,
                    unit_price=product.price,
                    total_price=product.price * quantity,
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:
            # Two requests raced with the same Idempotency-Key; the loser
            # returns whatever the winner created.
            replay = Order.objects.filter(
                user=request.user, idempotency_key=idempotency_key
            ).first()
            if replay:
                return Response(OrderSerializer(replay).data)
            raise

        logger.info(
            'order created id=%s user=%s product=%s quantity=%s',
            order.id, request.user.id, product.id, quantity,
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    pagination_class = ProductPagination
    permission_classes = [permissions.IsAuthenticated]
    lookup_value_regex = r'[0-9]+'

    def get_queryset(self):
        queryset = Order.objects.select_related('product', 'user')
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health(request):
    try:
        connection.ensure_connection()
    except DatabaseError:
        logger.exception('health check failed: database unreachable')
        return Response({'status': 'error', 'database': 'unreachable'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'status': 'ok', 'database': 'ok'})
