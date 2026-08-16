import logging
import threading
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection, connections
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import UserRateThrottle

from .models import Order, Product
from .throttling import PurchaseRateThrottle


class ApiTestCase(APITestCase):
    """Base class: clears the throttle cache so tests do not rate-limit each other."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.staff = User.objects.create_user('staff', password='pw', is_staff=True)
        self.shopper = User.objects.create_user('shopper', password='pw')

    def as_staff(self):
        self.client.force_authenticate(user=self.staff)

    def as_shopper(self):
        self.client.force_authenticate(user=self.shopper)


class ProductCRUDTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.as_staff()
        self.keyboard = Product.objects.create(
            name='Mechanical Keyboard',
            description='Blue switches',
            price=Decimal('2499.50'),
            stock=15,
        )
        self.mouse = Product.objects.create(
            name='Wireless Mouse',
            description='Ergonomic',
            price=Decimal('799.00'),
            stock=40,
        )

    def test_list_returns_all_products_in_a_paginated_envelope(self):
        response = self.client.get(reverse('product-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertEqual(len(response.data['results']), 2)

    def test_retrieve_returns_a_single_product(self):
        response = self.client.get(reverse('product-detail', args=[self.mouse.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Wireless Mouse')
        self.assertEqual(response.data['price'], '799.00')

    def test_retrieve_unknown_id_returns_404(self):
        response = self.client.get(reverse('product-detail', args=[9999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_product(self):
        payload = {
            'name': 'USB-C Hub',
            'description': '7-in-1 hub',
            'price': '1899.00',
            'stock': 25,
        }

        response = self.client.post(reverse('product-list'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 3)
        created = Product.objects.get(id=response.data['id'])
        self.assertEqual(created.price, Decimal('1899.00'))
        self.assertEqual(created.stock, 25)

    def test_create_rejects_missing_and_invalid_fields(self):
        cases = [
            ({}, 'name'),
            ({'name': '   ', 'price': '10.00'}, 'name'),
            ({'name': 'X', 'price': '-5.00'}, 'price'),
            ({'name': 'X', 'price': 'abc'}, 'price'),
            ({'name': 'X', 'price': '10.00', 'stock': -1}, 'stock'),
        ]

        for payload, expected_error_field in cases:
            with self.subTest(payload=payload):
                response = self.client.post(reverse('product-list'), payload, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(expected_error_field, response.data)

    def test_put_replaces_every_field(self):
        payload = {
            'name': 'Mechanical Keyboard V2',
            'description': 'Red switches',
            'price': '2999.00',
            'stock': 5,
        }

        response = self.client.put(
            reverse('product-detail', args=[self.keyboard.id]), payload, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.keyboard.refresh_from_db()
        self.assertEqual(self.keyboard.name, 'Mechanical Keyboard V2')
        self.assertEqual(self.keyboard.stock, 5)

    def test_put_requires_all_fields(self):
        response = self.client.put(
            reverse('product-detail', args=[self.keyboard.id]),
            {'name': 'Only a name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', response.data)

    def test_patch_updates_only_the_given_field(self):
        response = self.client.patch(
            reverse('product-detail', args=[self.keyboard.id]),
            {'stock': 99},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.keyboard.refresh_from_db()
        self.assertEqual(self.keyboard.stock, 99)
        self.assertEqual(self.keyboard.name, 'Mechanical Keyboard')

    def test_delete_removes_the_product(self):
        response = self.client.delete(reverse('product-detail', args=[self.mouse.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=self.mouse.id).exists())

    def test_delete_unknown_id_returns_404(self):
        response = self.client.delete(reverse('product-detail', args=[9999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_is_refused_when_the_product_has_orders(self):
        Order.objects.create(
            product=self.mouse, user=self.shopper, quantity=1,
            unit_price=self.mouse.price, total_price=self.mouse.price,
        )

        response = self.client.delete(reverse('product-detail', args=[self.mouse.id]))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Product.objects.filter(id=self.mouse.id).exists())


class PermissionTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(
            name='Wireless Mouse', price=Decimal('799.00'), stock=10
        )
        self.payload = {'name': 'New', 'price': '10.00', 'stock': 1}

    def test_anonymous_users_can_read(self):
        urls = [reverse('product-list'), reverse('product-detail', args=[self.product.id])]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_anonymous_users_cannot_write(self):
        cases = [
            ('post', reverse('product-list'), self.payload),
            ('put', reverse('product-detail', args=[self.product.id]), self.payload),
            ('patch', reverse('product-detail', args=[self.product.id]), {'stock': 1}),
            ('delete', reverse('product-detail', args=[self.product.id]), None),
            ('post', reverse('product-purchase', args=[self.product.id]), {'quantity': 1}),
        ]

        for method, url, payload in cases:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, payload, format='json')
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_signed_in_non_staff_users_cannot_change_the_catalogue(self):
        self.as_shopper()

        cases = [
            ('post', reverse('product-list'), self.payload),
            ('patch', reverse('product-detail', args=[self.product.id]), {'stock': 1}),
            ('delete', reverse('product-detail', args=[self.product.id]), None),
        ]

        for method, url, payload in cases:
            with self.subTest(method=method):
                response = getattr(self.client, method)(url, payload, format='json')
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_change_the_catalogue(self):
        self.as_staff()

        response = self.client.post(reverse('product-list'), self.payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_signed_in_non_staff_users_can_purchase(self):
        self.as_shopper()

        response = self.client.post(
            reverse('product-purchase', args=[self.product.id]), {'quantity': 1}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_jwt_token_endpoint_issues_a_working_token(self):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'shopper', 'password': 'pw'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
        purchase = client.post(
            reverse('product-purchase', args=[self.product.id]), {'quantity': 1}, format='json'
        )
        self.assertEqual(purchase.status_code, status.HTTP_201_CREATED)

    def test_bad_credentials_are_rejected(self):
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'shopper', 'password': 'wrong'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProductSearchAndFilterTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        Product.objects.create(name='Wireless Mouse', price=Decimal('799.00'), stock=10)
        Product.objects.create(name='Wireless Keyboard', price=Decimal('1500.00'), stock=10)
        Product.objects.create(name='Monitor 27 inch', price=Decimal('18999.00'), stock=10)

    def _names(self, response):
        return sorted(item['name'] for item in response.data['results'])

    def test_search_matches_a_partial_case_insensitive_name(self):
        response = self.client.get(reverse('product-list'), {'search': 'wire'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(self._names(response), ['Wireless Keyboard', 'Wireless Mouse'])

    def test_search_with_no_match_returns_an_empty_page(self):
        response = self.client.get(reverse('product-list'), {'search': 'zzz'})

        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['results'], [])

    def test_search_does_not_treat_input_as_a_sql_wildcard(self):
        response = self.client.get(reverse('product-list'), {'search': '%'})

        self.assertEqual(response.data['count'], 0)

    def test_min_and_max_price_filters(self):
        response = self.client.get(reverse('product-list'), {'min_price': '1000'})
        self.assertEqual(self._names(response), ['Monitor 27 inch', 'Wireless Keyboard'])

        response = self.client.get(reverse('product-list'), {'max_price': '1000'})
        self.assertEqual(self._names(response), ['Wireless Mouse'])

        response = self.client.get(
            reverse('product-list'), {'min_price': '800', 'max_price': '2000'}
        )
        self.assertEqual(self._names(response), ['Wireless Keyboard'])

    def test_search_and_price_filter_combine(self):
        response = self.client.get(
            reverse('product-list'), {'search': 'wireless', 'max_price': '1000'}
        )

        self.assertEqual(self._names(response), ['Wireless Mouse'])

    def test_invalid_price_filters_return_400(self):
        cases = [
            {'min_price': 'cheap'},
            {'max_price': 'NaN'},
            {'min_price': '-1'},
            {'min_price': '500', 'max_price': '100'},
        ]

        for params in cases:
            with self.subTest(params=params):
                response = self.client.get(reverse('product-list'), params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PaginationTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        for index in range(25):
            Product.objects.create(
                name=f'Product {index:02d}', price=Decimal('10.00'), stock=1
            )

    def test_first_page_holds_the_default_page_size(self):
        response = self.client.get(reverse('product-list'))

        self.assertEqual(response.data['count'], 25)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])

    def test_last_page_holds_the_remainder(self):
        response = self.client.get(reverse('product-list'), {'page': 3})

        self.assertEqual(len(response.data['results']), 5)
        self.assertIsNone(response.data['next'])

    def test_page_size_can_be_overridden(self):
        response = self.client.get(reverse('product-list'), {'page_size': 5})

        self.assertEqual(len(response.data['results']), 5)

    def test_page_size_is_capped(self):
        response = self.client.get(reverse('product-list'), {'page_size': 99999})

        self.assertEqual(len(response.data['results']), 25)

    def test_out_of_range_page_returns_404(self):
        response = self.client.get(reverse('product-list'), {'page': 99})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PurchaseTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.as_shopper()
        self.product = Product.objects.create(
            name='Portable SSD 1TB', price=Decimal('7499.00'), stock=10
        )
        self.url = reverse('product-purchase', args=[self.product.id])

    def test_successful_purchase_decreases_stock(self):
        response = self.client.post(self.url, {'quantity': 2}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['quantity'], 2)
        self.assertEqual(response.data['remaining_stock'], 8)
        self.assertEqual(response.data['total_price'], '14998.00')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_successful_purchase_records_an_order(self):
        self.client.post(self.url, {'quantity': 3}, format='json')

        order = Order.objects.get()
        self.assertEqual(order.user, self.shopper)
        self.assertEqual(order.product, self.product)
        self.assertEqual(order.quantity, 3)
        self.assertEqual(order.unit_price, Decimal('7499.00'))
        self.assertEqual(order.total_price, Decimal('22497.00'))

    def test_order_keeps_the_price_paid_when_the_product_price_changes_later(self):
        self.client.post(self.url, {'quantity': 1}, format='json')

        self.product.price = Decimal('1.00')
        self.product.save(update_fields=['price'])

        order = Order.objects.get()
        self.assertEqual(order.unit_price, Decimal('7499.00'))

    def test_purchasing_the_entire_stock_is_allowed(self):
        response = self.client.post(self.url, {'quantity': 10}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_purchase_larger_than_stock_fails_and_leaves_stock_untouched(self):
        response = self.client.post(self.url, {'quantity': 11}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', response.data['detail'])
        self.assertEqual(response.data['available_stock'], 10)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertFalse(Order.objects.exists())

    def test_invalid_quantities_are_rejected(self):
        cases = [{'quantity': 0}, {'quantity': -3}, {'quantity': 'two'}, {}]

        for payload in cases:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('quantity', response.data)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertFalse(Order.objects.exists())

    def test_purchasing_an_unknown_product_returns_404(self):
        response = self.client.post(
            reverse('product-purchase', args=[9999]), {'quantity': 1}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_purchase_only_accepts_post(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class IdempotencyTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.as_shopper()
        self.product = Product.objects.create(
            name='Portable SSD 1TB', price=Decimal('7499.00'), stock=10
        )
        self.url = reverse('product-purchase', args=[self.product.id])

    def test_replaying_a_request_with_the_same_key_does_not_buy_twice(self):
        first = self.client.post(
            self.url, {'quantity': 2}, format='json', HTTP_IDEMPOTENCY_KEY='abc-123'
        )
        second = self.client.post(
            self.url, {'quantity': 2}, format='json', HTTP_IDEMPOTENCY_KEY='abc-123'
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['id'], second.data['id'])

        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_different_keys_are_separate_purchases(self):
        self.client.post(self.url, {'quantity': 1}, format='json', HTTP_IDEMPOTENCY_KEY='k1')
        self.client.post(self.url, {'quantity': 1}, format='json', HTTP_IDEMPOTENCY_KEY='k2')

        self.assertEqual(Order.objects.count(), 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_the_same_key_from_a_different_user_is_a_separate_purchase(self):
        self.client.post(self.url, {'quantity': 1}, format='json', HTTP_IDEMPOTENCY_KEY='same')

        self.client.force_authenticate(user=self.staff)
        self.client.post(self.url, {'quantity': 1}, format='json', HTTP_IDEMPOTENCY_KEY='same')

        self.assertEqual(Order.objects.count(), 2)

    def test_purchases_without_a_key_are_never_deduplicated(self):
        self.client.post(self.url, {'quantity': 1}, format='json')
        self.client.post(self.url, {'quantity': 1}, format='json')

        self.assertEqual(Order.objects.count(), 2)


class OrderHistoryTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(
            name='Desk Lamp', price=Decimal('999.00'), stock=10
        )
        self.shopper_order = Order.objects.create(
            product=self.product, user=self.shopper, quantity=1,
            unit_price=Decimal('999.00'), total_price=Decimal('999.00'),
        )
        self.staff_order = Order.objects.create(
            product=self.product, user=self.staff, quantity=2,
            unit_price=Decimal('999.00'), total_price=Decimal('1998.00'),
        )

    def test_anonymous_users_cannot_see_orders(self):
        response = self.client.get(reverse('order-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_user_sees_only_their_own_orders(self):
        self.as_shopper()

        response = self.client.get(reverse('order-list'))

        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.shopper_order.id)

    def test_a_user_cannot_open_someone_elses_order(self):
        self.as_shopper()

        response = self.client.get(reverse('order-detail', args=[self.staff_order.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_see_every_order(self):
        self.as_staff()

        response = self.client.get(reverse('order-list'))

        self.assertEqual(response.data['count'], 2)

    def test_orders_are_read_only(self):
        self.as_staff()

        response = self.client.post(
            reverse('order-list'), {'product': self.product.id, 'quantity': 1}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class ThrottleTests(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.as_shopper()
        self.product = Product.objects.create(
            name='Desk Lamp', price=Decimal('999.00'), stock=100
        )

    def test_purchase_endpoint_is_rate_limited(self):
        url = reverse('product-purchase', args=[self.product.id])

        with patch.dict(PurchaseRateThrottle.THROTTLE_RATES, {'purchase': '2/min'}):
            codes = [
                self.client.post(url, {'quantity': 1}, format='json').status_code
                for _ in range(4)
            ]

        self.assertEqual(codes[:2], [status.HTTP_201_CREATED, status.HTTP_201_CREATED])
        self.assertEqual(codes[2:], [status.HTTP_429_TOO_MANY_REQUESTS] * 2)
        self.assertEqual(Order.objects.count(), 2)

    def test_the_configured_purchase_rate_is_stricter_than_the_general_user_rate(self):
        purchase_rate = PurchaseRateThrottle().num_requests
        user_rate = UserRateThrottle().num_requests

        self.assertLess(purchase_rate, user_rate)


class HealthTests(ApiTestCase):

    def test_health_is_public_and_reports_ok(self):
        response = self.client.get(reverse('health'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')


class ConcurrentPurchaseTests(TransactionTestCase):
    """Proves the row lock prevents overselling.

    Skipped on SQLite, which does not support SELECT ... FOR UPDATE, so the
    lock is a no-op there. Runs on PostgreSQL.
    """

    BUYERS = 20
    STOCK = 5

    @skipUnless(
        connection.features.has_select_for_update,
        'database backend does not support row locking',
    )
    def test_concurrent_purchases_never_oversell(self):
        cache.clear()
        product = Product.objects.create(
            name='Race Item', price=Decimal('100.00'), stock=self.STOCK
        )
        users = [
            User.objects.create_user(f'buyer{i}', password='pw')
            for i in range(self.BUYERS)
        ]
        url = reverse('product-purchase', args=[product.id])

        barrier = threading.Barrier(self.BUYERS)
        results = []
        results_lock = threading.Lock()

        def buy(user):
            try:
                client = APIClient()
                client.force_authenticate(user=user)
                barrier.wait()
                response = client.post(url, {'quantity': 1}, format='json')
                with results_lock:
                    results.append(response.status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=buy, args=(user,)) for user in users]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        sold = results.count(status.HTTP_201_CREATED)
        product.refresh_from_db()

        self.assertEqual(sold, self.STOCK)
        self.assertEqual(product.stock, 0)
        self.assertEqual(Order.objects.count(), self.STOCK)
