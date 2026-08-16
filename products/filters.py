from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError


def parse_price(raw, field_name):
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({field_name: f"'{raw}' is not a valid number."}) from exc

    if not value.is_finite():
        raise ValidationError({field_name: f"'{raw}' is not a valid number."})

    if value < 0:
        raise ValidationError({field_name: 'Must be zero or greater.'})

    return value


def filter_products(queryset, params):
    search = (params.get('search') or '').strip()
    if search:
        queryset = queryset.filter(name__icontains=search)

    min_price = params.get('min_price') or None
    max_price = params.get('max_price') or None

    if min_price is not None:
        min_price = parse_price(min_price, 'min_price')
        queryset = queryset.filter(price__gte=min_price)

    if max_price is not None:
        max_price = parse_price(max_price, 'max_price')
        queryset = queryset.filter(price__lte=max_price)

    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValidationError(
            {'min_price': 'min_price cannot be greater than max_price.'}
        )

    return queryset
