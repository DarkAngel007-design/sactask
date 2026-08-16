# Product API

A Product API built with Django and Django REST Framework, supporting CRUD,
search, price filtering, pagination, and a purchase endpoint that decreases stock.

Reads are public. Changing the catalogue requires a staff account, and purchasing
requires a signed-in user, so the endpoints that spend stock or change data are not
open to anonymous callers.

## Setup

Requires Python 3.10+. Runs on SQLite out of the box; no configuration needed.

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

### Create accounts to test with

Writes need a staff user and purchases need any signed-in user:

```bash
DJANGO_SUPERUSER_PASSWORD=admin-pw-12345 python manage.py createsuperuser \
  --username admin --email admin@example.com --noinput
```

Get a token:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin-pw-12345"}'
```

```json
{"access": "eyJhbGciOi...", "refresh": "eyJhbGciOi..."}
```

Send the access token on every request that changes something:

```bash
-H "Authorization: Bearer <access token>"
```

Access tokens last 30 minutes. Exchange a refresh token for a new one at
`POST /api/auth/token/refresh/` with `{"refresh": "..."}`.

## Who can do what

| Action | Anonymous | Signed in | Staff |
|---|---|---|---|
| List / view products | yes | yes | yes |
| Create / update / delete products | no (401) | no (403) | yes |
| Purchase | no (401) | yes | yes |
| View own orders | no (401) | yes | yes |
| View everyone's orders | no | no | yes |

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

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/api/products/` | none | List products |
| POST | `/api/products/` | staff | Create a product |
| GET | `/api/products/{id}/` | none | Get one product |
| PUT | `/api/products/{id}/` | staff | Update a product (all fields) |
| PATCH | `/api/products/{id}/` | staff | Update a product (some fields) |
| DELETE | `/api/products/{id}/` | staff | Delete a product |
| POST | `/api/products/{id}/purchase/` | user | Buy units and reduce stock |
| GET | `/api/orders/` | user | Purchase history |
| GET | `/api/orders/{id}/` | user | One order |
| POST | `/api/auth/token/` | none | Get an access and refresh token |
| POST | `/api/auth/token/refresh/` | none | Get a new access token |
| GET | `/api/health/` | none | Service and database status |

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

### Create (staff)

```bash
curl -X POST "http://127.0.0.1:8000/api/products/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "USB-C Hub", "description": "7-in-1 hub", "price": "1899.00", "stock": 25}'
```

Returns `201 Created` with the new product.

### Update (staff)

```bash
curl -X PUT "http://127.0.0.1:8000/api/products/13/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "USB-C Hub Pro", "description": "8-in-1 hub", "price": "2299.00", "stock": 20}'
```

```bash
curl -X PATCH "http://127.0.0.1:8000/api/products/13/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"stock": 5}'
```

### Delete (staff)

```bash
curl -X DELETE "http://127.0.0.1:8000/api/products/13/" \
  -H "Authorization: Bearer $TOKEN"
```

Returns `204 No Content`. A product that already has orders cannot be deleted, so
that purchase history is never orphaned — that returns `409 Conflict`.

### Purchase

```bash
curl -X POST "http://127.0.0.1:8000/api/products/1/purchase/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"quantity": 2}'
```

`201 Created`

```json
{
  "id": 1,
  "product": 1,
  "product_name": "Wireless Mouse",
  "quantity": 2,
  "unit_price": "799.00",
  "total_price": "1598.00",
  "remaining_stock": 38,
  "created_at": "2026-01-05T10:30:00.000000Z"
}
```

Every purchase writes an `Order` row, so there is a permanent record of why stock
changed. `unit_price` is copied at purchase time, so changing a product's price
later does not rewrite past orders.

If the quantity is more than the stock, the purchase fails and the stock is left
unchanged:

```json
{
  "detail": "Insufficient stock: requested 9999, only 38 available.",
  "available_stock": 38
}
```

### Safe retries

If a request times out you cannot tell whether it succeeded. Send an
`Idempotency-Key` header and retrying is safe — the second call returns the
original order with `200 OK` instead of buying again:

```bash
curl -X POST "http://127.0.0.1:8000/api/products/1/purchase/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7" \
  -d '{"quantity": 2}'
```

Keys are scoped per user. Any unique string works; a UUID is a good choice.

## Rate limits

| Scope | Default |
|---|---|
| Anonymous requests | 60/min |
| Signed-in requests | 240/min |
| Purchases | 10/min |

Exceeding a limit returns `429 Too Many Requests`. All three are configurable in
`.env`.

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
| No token on an endpoint that needs one | 401 |
| Signed in but not allowed (non-staff writing) | 403 |
| Product id does not exist | 404 |
| Page number past the last page | 404 |
| Wrong method, e.g. GET on the purchase URL | 405 |
| Deleting a product that has orders | 409 |
| Rate limit exceeded | 429 |

Errors come back as JSON, for example:

```json
{"quantity": ["Ensure this value is greater than or equal to 1."]}
```

## Configuration

Every setting has a development-safe default. Copy `.env.example` to `.env` to
change any of them.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev key | Required when `DJANGO_DEBUG=False` |
| `DJANGO_DEBUG` | `True` | Turn off in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hostnames the app answers on |
| `DATABASE_URL` | SQLite file | e.g. `postgres://user:pass@host:5432/db` |
| `DJANGO_THROTTLE_*` | see above | Rate limits |
| `DJANGO_ACCESS_TOKEN_MINUTES` | `30` | Access token lifetime |

When `DJANGO_DEBUG=False`, the app refuses to start without a real
`DJANGO_SECRET_KEY` and a real `DJANGO_ALLOWED_HOSTS`, rather than falling back to
insecure values.

## Running with PostgreSQL

SQLite is fine for development, but it does not support row-level locking, which
the purchase endpoint relies on to prevent overselling. Point `DATABASE_URL` at
PostgreSQL for anything real — no other change is needed:

```bash
export DATABASE_URL=postgres://user:pass@localhost:5432/product_api
python manage.py migrate
python manage.py test        # the concurrency test now runs instead of skipping
```

In production, serve it with gunicorn behind a reverse proxy rather than
`runserver`:

```bash
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

## Tests

```bash
python manage.py test
```

50 tests in `products/tests.py`:

- `ProductCRUDTests` — list, get, create, update, delete, and their error cases
- `PermissionTests` — who can read, write and purchase; JWT login
- `ProductSearchAndFilterTests` — search, price filters, invalid filters
- `PaginationTests` — page size, caps and page boundaries
- `PurchaseTests` — successful purchase, buying all stock, overselling,
  invalid quantities, unknown product, wrong method
- `IdempotencyTests` — replayed requests do not buy twice
- `OrderHistoryTests` — users see only their own orders
- `ThrottleTests` — the purchase rate limit
- `HealthTests` — the health endpoint
- `ConcurrentPurchaseTests` — 20 simultaneous buyers cannot oversell 5 units.
  **Skipped on SQLite**, which has no row locking; it runs on PostgreSQL.

Lint and deployment checks, the same ones CI runs:

```bash
pip install -r requirements-dev.txt
ruff check .
DJANGO_DEBUG=False DJANGO_SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key as k; print(k())") \
  DJANGO_ALLOWED_HOSTS=example.com python manage.py check --deploy --fail-level WARNING
```

GitHub Actions runs lint, the suite on both SQLite and PostgreSQL, the deployment
checks, and a check that no migration is missing.

## Project structure

```
config/          settings and root URLs
products/
  models.py      Product and Order
  serializers.py validation and JSON conversion
  views.py       ProductViewSet (CRUD + purchase), OrderViewSet, health
  permissions.py who is allowed to do what
  throttling.py  the purchase rate limit
  filters.py     search and price filtering
  pagination.py  pagination settings
  urls.py        router and auth routes
  tests.py       tests
.github/workflows/ci.yml
manage.py
requirements.txt
```

## Notes

- `price` uses `DecimalField` rather than `FloatField` so money is stored exactly.
- The purchase endpoint runs inside a transaction and reads the row with
  `select_for_update()`, so two purchases at the same time cannot both sell the
  last item. SQLite ignores the lock, which is why the concurrency test is
  Postgres-only.
- `Order.unit_price` is a copy, not a lookup, so price changes do not rewrite
  history. Products with orders cannot be deleted (`on_delete=PROTECT`).
- `Meta.ordering = ['id']` gives the list a fixed order, otherwise the same
  product could show up on two different pages.
- Filtering is written directly in `filters.py` instead of using `django-filter`,
  so an invalid value like `?min_price=abc` returns a 400 instead of being ignored.
- The default DRF permission is `IsAuthenticated`, so a new endpoint is private
  unless it deliberately opts out. Public access is granted per view, not assumed.
- The browsable HTML API is only enabled when `DEBUG` is on; production returns
  JSON only.
