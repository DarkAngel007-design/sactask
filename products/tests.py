from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Product


class ProductCRUDTests(APITestCase):
    def setUp(self):
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
        response = self.client.get(
            reverse('product-detail', args=[self.mouse.id])
        )

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
                response = self.client.post(
                    reverse('product-list'), payload, format='json'
                )
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
        response = self.client.delete(
            reverse('product-detail', args=[self.mouse.id])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(id=self.mouse.id).exists())

    def test_delete_unknown_id_returns_404(self):
        response = self.client.delete(reverse('product-detail', args=[9999]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ProductSearchAndFilterTests(APITestCase):
    def setUp(self):
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


class PaginationTests(APITestCase):

    def setUp(self):
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

    def test_out_of_range_page_returns_404(self):
        response = self.client.get(reverse('product-list'), {'page': 99})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PurchaseTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Portable SSD 1TB', price=Decimal('7499.00'), stock=10
        )
        self.url = reverse('product-purchase', args=[self.product.id])

    def test_successful_purchase_decreases_stock(self):
        response = self.client.post(self.url, {'quantity': 2}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quantity_purchased'], 2)
        self.assertEqual(response.data['remaining_stock'], 8)
        self.assertEqual(response.data['total_price'], '14998.00')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_purchasing_the_entire_stock_is_allowed(self):
        response = self.client.post(self.url, {'quantity': 10}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_purchase_larger_than_stock_fails_and_leaves_stock_untouched(self):
        response = self.client.post(self.url, {'quantity': 11}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Insufficient stock', response.data['detail'])
        self.assertEqual(response.data['available_stock'], 10)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_invalid_quantities_are_rejected(self):
        cases = [{'quantity': 0}, {'quantity': -3}, {'quantity': 'two'}, {}]

        for payload in cases:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('quantity', response.data)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_purchasing_an_unknown_product_returns_404(self):
        response = self.client.post(
            reverse('product-purchase', args=[9999]), {'quantity': 1}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_purchase_only_accepts_post(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
