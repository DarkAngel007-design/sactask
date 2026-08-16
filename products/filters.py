"""Query-parameter filtering for the product list endpoint.

Kept out of views.py so the view stays short and this logic can be unit-tested
on its own.
"""

from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError


def parse_price(raw, field_name):
    """Turn a raw ?min_price=... string into a Decimal, or raise HTTP 400."""
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field_name: f"'{raw}' is not a valid number."})

    if not value.is_finite():  # rejects 'NaN' and 'Infinity'
        raise ValidationError({field_name: f"'{raw}' is not a valid number."})

    if value < 0:
        raise ValidationError({field_name: 'Must be zero or greater.'})

    return value


def filter_products(queryset, params):
    """Apply ?search=, ?min_price= and ?max_price= to a Product queryset.

    Nothing hits the database here -- querysets are lazy, so this just builds
    up the WHERE clause that the paginator will later execute.
    """
    search = (params.get('search') or '').strip()
    if search:
        # icontains -> SQL "WHERE name LIKE '%search%'", case-insensitive.
        queryset = queryset.filter(name__icontains=search)

    min_price = params.get('min_price')
    max_price = params.get('max_price')

    if min_price not in (None, ''):
        min_price = parse_price(min_price, 'min_price')
        queryset = queryset.filter(price__gte=min_price)  # >=
    else:
        min_price = None

    if max_price not in (None, ''):
        max_price = parse_price(max_price, 'max_price')
        queryset = queryset.filter(price__lte=max_price)  # <=
    else:
        max_price = None

    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValidationError(
            {'min_price': 'min_price cannot be greater than max_price.'}
        )

    return queryset
