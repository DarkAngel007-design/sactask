# Product API

A Product API built with Django and Django REST Framework, supporting CRUD,
search, price filtering, pagination, and a purchase endpoint that decreases stock.

## Setup

Requires Python 3.10+.

```bash
git clone <repo-url>
cd product-api

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_products  # optional: adds 12 sample products
python manage.py runserver
```

The API runs at http://127.0.0.1:8000/api/products/

Opening that URL in a browser gives DRF's browsable API, where you can try the
endpoints from a form.

## Product fields

| Field | Type | Notes |
|---|---|---|
| `id` | integer | read-only |
| `name` | string | required, max 200 characters |
| `description` | string | optional |
| `price` | decimal | required, must be 0 or more |
| `stock` | integer | optional, defaults to 0, must be 0 or more |
| `created_at` | datetime | read-only |
| `updated_at` | datetime | read-only |

`price` is returned as a string (`"799.00"`) because it is stored as a decimal,
not a float, to avoid rounding errors on money.

## Endpoints

| Method | URL | Description |
|---|---|---|
| GET | `/api/products/` | List products |
| POST | `/api/products/` | Create a product |
| GET | `/api/products/{id}/` | Get one product |
| PUT | `/api/products/{id}/` | Update a product (all fields) |
| PATCH | `/api/products/{id}/` | Update a product (some fields) |
| DELETE | `/api/products/{id}/` | Delete a product |
| POST | `/api/products/{id}/purchase/` | Buy units and reduce stock |

### Query parameters on the list endpoint

| Parameter | Example | Description |
|---|---|---|
| `search` | `?search=mouse` | Partial, case-insensitive match on name |
| `min_price` | `?min_price=500` | Price greater than or equal to |
| `max_price` | `?max_price=3000` | Price less than or equal to |
| `page` | `?page=2` | Page number, default 1 |
| `page_size` | `?page_size=25` | Items per page, default 10, max 100 |

These can be combined:

```
/api/products/?search=laptop&min_price=500&max_price=5000&page=1&page_size=5
```

## Example requests

### List products

```bash
curl "http://127.0.0.1:8000/api/products/?page_size=2"
```

```json
{
  "count": 12,
  "next": "http://127.0.0.1:8000/api/products/?page=2&page_size=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Wireless Mouse",
      "description": "Ergonomic 2.4GHz wireless mouse.",
      "price": "799.00",
      "stock": 40,
      "created_at": "2026-01-05T10:12:00.123456Z",
      "updated_at": "2026-01-05T10:12:00.123456Z"
    },
    {
      "id": 2,
      "name": "Mechanical Keyboard",
      "description": "Blue-switch mechanical keyboard, 87 keys.",
      "price": "2499.50",
      "stock": 15,
      "created_at": "2026-01-05T10:12:00.130000Z",
      "updated_at": "2026-01-05T10:12:00.130000Z"
    }
  ]
}
```

### Search by partial name

```bash
curl "http://127.0.0.1:8000/api/products/?search=lap"
```

### Filter by price

```bash
curl "http://127.0.0.1:8000/api/products/?min_price=1000&max_price=3000"
```

### Get one product

```bash
curl "http://127.0.0.1:8000/api/products/1/"
```

### Create

```bash
curl -X POST "http://127.0.0.1:8000/api/products/" \
  -H "Content-Type: application/json" \
  -d '{"name": "USB-C Hub", "description": "7-in-1 hub", "price": "1899.00", "stock": 25}'
```

Returns `201 Created` with the new product.

### Update

```bash
curl -X PUT "http://127.0.0.1:8000/api/products/13/" \
  -H "Content-Type: application/json" \
  -d '{"name": "USB-C Hub Pro", "description": "8-in-1 hub", "price": "2299.00", "stock": 20}'
```

```bash
curl -X PATCH "http://127.0.0.1:8000/api/products/13/" \
  -H "Content-Type: application/json" \
  -d '{"stock": 5}'
```

### Delete

```bash
curl -X DELETE "http://127.0.0.1:8000/api/products/13/"
```

Returns `204 No Content`.

### Purchase

```bash
curl -X POST "http://127.0.0.1:8000/api/products/1/purchase/" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 2}'
```

```json
{
  "id": 1,
  "name": "Wireless Mouse",
  "quantity_purchased": 2,
  "remaining_stock": 38,
  "total_price": "1598.00"
}
```

If the quantity is more than the stock, the purchase fails and the stock is
left unchanged:

```json
{
  "detail": "Insufficient stock: requested 9999, only 38 available.",
  "available_stock": 38
}
```

## Errors

| Situation | Status |
|---|---|
| Missing or invalid field on create | 400 |
| Blank name | 400 |
| Negative price or stock | 400 |
| `?min_price=abc` or a negative price filter | 400 |
| `min_price` greater than `max_price` | 400 |
| Purchase quantity of 0, negative, or not a number | 400 |
| Purchase quantity greater than stock | 400 |
| Product id does not exist | 404 |
| Page number past the last page | 404 |
| Wrong method, e.g. GET on the purchase URL | 405 |

Errors come back as JSON, for example:

```json
{"quantity": ["Ensure this value is greater than or equal to 1."]}
```

## Tests

```bash
python manage.py test
```

25 tests in `products/tests.py`, split into four classes:

- `ProductCRUDTests` — list, get, create, update, delete, and their error cases
- `ProductSearchAndFilterTests` — search, price filters, invalid filters
- `PaginationTests` — page size and page boundaries
- `PurchaseTests` — successful purchase, buying all stock, overselling,
  invalid quantities, unknown product, wrong method

## Project structure

```
config/          settings and root URLs
products/
  models.py      Product model
  serializers.py validation and JSON conversion
  views.py       ProductViewSet (CRUD + purchase)
  filters.py     search and price filtering
  pagination.py  pagination settings
  urls.py        router
  tests.py       tests
manage.py
requirements.txt
```

## Notes

- `price` uses `DecimalField` rather than `FloatField` so money is stored
  exactly.
- The purchase endpoint runs inside a transaction and reads the row with
  `select_for_update()`, so two purchases at the same time cannot both sell the
  last item. SQLite ignores the lock, but it works on PostgreSQL and MySQL.
- `Meta.ordering = ['id']` gives the list a fixed order, otherwise the same
  product could show up on two different pages.
- Filtering is written directly in `filters.py` instead of using `django-filter`,
  so an invalid value like `?min_price=abc` returns a 400 instead of being
  ignored.
- There is no authentication, as the task did not ask for it.
