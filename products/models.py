from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    """A single item in the catalogue."""

    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True, default='')

    # DecimalField (not FloatField) because money must not suffer from binary
    # floating-point rounding errors. 10 digits total, 2 after the point.
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    # PositiveIntegerField makes "negative stock" impossible at the DB level.
    stock = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A stable default order, otherwise pagination can repeat or skip rows.
        ordering = ['id']

    def __str__(self):
        return self.name
