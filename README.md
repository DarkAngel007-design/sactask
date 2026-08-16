# Product API

A REST API for a product catalogue, built with **Django** and **Django REST Framework**.

It supports full CRUD on products, partial-name search, price-range filtering,
pagination, and a purchase endpoint that safely decrements stock.

---

## Contents

- [Setup](#setup)
- [Endpoints](#endpoints)
- [Example requests](#example-requests)
- [Validation and error handling](#validation-and-error-handling)
- [Running the tests](#running-the-tests)
- [Project structure](#project-structure)
- [Design notes](#design-notes)

---

## Setup

Requires Python 3.10 or newer.

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd product-api

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create the database tables
python manage.py migrate

# 5. (Optional) Load 12 sample products
python manage.py seed_products

# 6. Run the server
python manage.py runserver
```

The API is now at **http://127.0.0.1:8000/api/products/**

Open that URL in a browser to use DRF's browsable API, which lets you try every
endpoint from a web form.

Optional admin site — create a login with `python manage.py createsuperuser`,
then visit http://127.0.0.1:8000/admin/.

### Configuration

The project runs with zero configuration for local development. For a real
deployment, set these environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | Cryptographic signing key |
| `DJANGO_DEBUG` | `true` | Set to `false` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames |

---

## Endpoints

Base path: `/api/products/`

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/products/` | List products (paginated, searchable, filterable) |
| `POST` | `/api/products/` | Create a product |
| `GET` | `/api/products/{id}/` | Retrieve one product |
| `PUT` | `/api/products/{id}/` | Replace a product (all fields required) |
| `PATCH` | `/api/products/{id}/` | Update selected fields |
| `DELETE` | `/api/products/{id}/` | Delete a product |
| `POST` | `/api/products/{id}/purchase/` | Buy N units, decrementing stock |

### Query parameters for `GET /api/products/`

| Parameter | Example | Meaning |
|---|---|---|
| `search` | `?search=key` | Case-insensitive **partial** match on `name` |
| `min_price` | `?min_price=500` | Only products with `price >= 500` |
| `max_price` | `?max_price=3000` | Only products with `price <= 3000` |
| `page` | `?page=2` | Page number (default `1`) |
| `page_size` | `?page_size=25` | Items per page (default `10`, max `100`) |

All parameters can be combined:
`/api/products/?search=laptop&min_price=500&max_price=5000&page=1&page_size=5`

### Product fields

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Read-only, auto-generated |
| `name` | string | Required, max 200 chars, cannot be blank |
| `description` | string | Optional |
| `price` | decimal string | Required, must be `>= 0`, 2 decimal places |
| `stock` | integer | Optional (default `0`), must be `>= 0` |
| `created_at` | datetime | Read-only |
| `updated_at` | datetime | Read-only |

`price` is returned as a JSON **string** (`"799.00"`) rather than a float. This is
DRF's default for `DecimalField` and avoids floating-point rounding errors on
money values.

---

## Example requests

### List products (paginated)

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

Matches `Laptop Stand` and `Laptop Sleeve 14 inch`.

### Filter by price range

```bash
curl "http://127.0.0.1:8000/api/products/?min_price=1000&max_price=3000"
```

### Retrieve one product

```bash
curl "http://127.0.0.1:8000/api/products/1/"
```

### Create a product

```bash
curl -X POST "http://127.0.0.1:8000/api/products/" \
  -H "Content-Type: application/json" \
  -d '{"name": "USB-C Hub", "description": "7-in-1 hub", "price": "1899.00", "stock": 25}'
```

`201 Created`

```json
{
  "id": 13,
  "name": "USB-C Hub",
  "description": "7-in-1 hub",
  "price": "1899.00",
  "stock": 25,
  "created_at": "2026-01-05T10:20:00.000000Z",
  "updated_at": "2026-01-05T10:20:00.000000Z"
}
```

### Update a product

Full replace — every required field must be present:

```bash
curl -X PUT "http://127.0.0.1:8000/api/products/13/" \
  -H "Content-Type: application/json" \
  -d '{"name": "USB-C Hub Pro", "description": "8-in-1 hub", "price": "2299.00", "stock": 20}'
```

Partial update — send only what changes:

```bash
curl -X PATCH "http://127.0.0.1:8000/api/products/13/" \
  -H "Content-Type: application/json" \
  -d '{"stock": 5}'
```

### Delete a product

```bash
curl -X DELETE "http://127.0.0.1:8000/api/products/13/"
```

`204 No Content`

### Purchase

```bash
curl -X POST "http://127.0.0.1:8000/api/products/1/purchase/" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 2}'
```

`200 OK`

```json
{
  "id": 1,
  "name": "Wireless Mouse",
  "quantity_purchased": 2,
  "remaining_stock": 38,
  "total_price": "1598.00"
}
```

Requesting more than is in stock leaves the stock untouched:

```bash
curl -X POST "http://127.0.0.1:8000/api/products/1/purchase/" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 9999}'
```

`400 Bad Request`

```json
{
  "detail": "Insufficient stock: requested 9999, only 38 available.",
  "available_stock": 38
}
```

---

## Validation and error handling

| Situation | Status | Response body |
|---|---|---|
| Missing required field on create | `400` | `{"name": ["This field is required."]}` |
| Blank / whitespace-only name | `400` | `{"name": ["Name cannot be blank."]}` |
| Negative price | `400` | `{"price": ["Ensure this value is greater than or equal to 0.00."]}` |
| Non-numeric price | `400` | `{"price": ["A valid number is required."]}` |
| Negative stock | `400` | `{"stock": ["Ensure this value is greater than or equal to 0."]}` |
| `?min_price=abc` | `400` | `{"min_price": "'abc' is not a valid number."}` |
| `?min_price=500&max_price=100` | `400` | `{"min_price": "min_price cannot be greater than max_price."}` |
| Purchase `quantity` of `0` or negative | `400` | `{"quantity": ["Ensure this value is greater than or equal to 1."]}` |
| Purchase `quantity` not an integer | `400` | `{"quantity": ["A valid integer is required."]}` |
| Purchase exceeding stock | `400` | `{"detail": "Insufficient stock: ...", "available_stock": 3}` |
| Unknown product id | `404` | `{"detail": "No Product matches the given query."}` |
| Page number past the end | `404` | `{"detail": "Invalid page."}` |
| `GET` on the purchase endpoint | `405` | `{"detail": "Method \"GET\" not allowed."}` |

---

## Running the tests

```bash
python manage.py test
```

25 tests covering CRUD, search, price filters, pagination, and purchase:

```
Ran 25 tests in 0.029s

OK
```

The suite is organised into four classes in `products/tests.py`:

- `ProductCRUDTests` — list, retrieve, create, `PUT`, `PATCH`, delete, and their 400/404 cases
- `ProductSearchAndFilterTests` — partial search, price bounds, combined filters, invalid filters
- `PaginationTests` — page size, page boundaries, out-of-range pages
- `PurchaseTests` — successful purchase, buying the whole stock, overselling, invalid quantities, unknown id, wrong HTTP method

Each test runs against a temporary database inside a transaction that is rolled
back afterwards, so tests never affect `db.sqlite3` and never depend on each
other's data.

---

## Project structure

```
product-api/
├── config/                 # Project-level configuration
│   ├── settings.py         # Installed apps, database, DRF settings
│   ├── urls.py             # Routes /api/ to the products app
│   ├── asgi.py / wsgi.py   # Web-server entry points
├── products/               # The application
│   ├── models.py           # Product model (the database table)
│   ├── serializers.py      # JSON <-> Python conversion + validation
│   ├── views.py            # ProductViewSet: CRUD + purchase action
│   ├── filters.py          # ?search / ?min_price / ?max_price handling
│   ├── pagination.py       # Page-number pagination settings
│   ├── urls.py             # Router that generates all product URLs
│   ├── admin.py            # Django admin registration
│   ├── tests.py            # 25 automated tests
│   ├── migrations/         # Versioned database schema changes
│   └── management/commands/seed_products.py   # Sample data loader
├── manage.py               # Django CLI entry point
├── requirements.txt
└── README.md
```

---

## Design notes

**`DecimalField` for price.** Money is stored as an exact decimal rather than a
float, so `0.1 + 0.2` problems cannot occur. It is serialised as a JSON string
for the same reason.

**Filtering written by hand.** `?search`, `?min_price` and `?max_price` are parsed
in `products/filters.py` instead of pulling in `django-filter`. It is a small
amount of code, it keeps the dependency list to Django + DRF, and it lets the API
return a precise 400 for a malformed value rather than silently ignoring it.

**Row locking on purchase.** The purchase endpoint runs inside
`transaction.atomic()` and reads the product with `select_for_update()`. Without
the lock, two purchases arriving at the same instant could both read
`stock = 1` and both succeed, driving stock negative. The lock forces the second
request to wait until the first commits. SQLite ignores the clause (it locks the
whole file anyway); on PostgreSQL or MySQL it is a genuine row lock.

**Numeric-only ids in URLs.** `lookup_value_regex = r'[0-9]+'` on the viewset means
`/api/products/abc/` fails to match any route and returns a clean `404`, instead of
reaching the database and raising a 500 while comparing `'abc'` to an integer column.

**Explicit ordering.** `Product.Meta.ordering = ['id']` guarantees a stable sort.
Without it, a paginated query has no defined order and the same row can appear on
two different pages.

**Stateless and unauthenticated.** The assignment does not ask for authentication,
so every endpoint is open. Adding it would mean setting
`DEFAULT_AUTHENTICATION_CLASSES` and `DEFAULT_PERMISSION_CLASSES` in
`config/settings.py` — no changes to the view logic.
