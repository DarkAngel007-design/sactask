from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class Order(models.Model):
    """A completed purchase. Kept as a permanent record of why stock changed."""

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='orders')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders'
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    # Copied from the product at purchase time, so later price changes do not
    # rewrite history.
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    idempotency_key = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'idempotency_key'],
                condition=~models.Q(idempotency_key=''),
                name='unique_idempotency_key_per_user',
            ),
        ]

    def __str__(self):
        return f'Order {self.pk}: {self.quantity} x {self.product_id}'
