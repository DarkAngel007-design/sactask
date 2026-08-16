"""Insert a handful of sample products so the API has something to return.

Usage:
    python manage.py seed_products
    python manage.py seed_products --flush   # wipe existing rows first
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from products.models import Product

SAMPLE_PRODUCTS = [
    ('Wireless Mouse', 'Ergonomic 2.4GHz wireless mouse.', '799.00', 40),
    ('Mechanical Keyboard', 'Blue-switch mechanical keyboard, 87 keys.', '2499.50', 15),
    ('USB-C Hub', '7-in-1 hub with HDMI and card reader.', '1899.00', 25),
    ('Laptop Stand', 'Aluminium adjustable laptop stand.', '1299.00', 0),
    ('Noise Cancelling Headphones', 'Over-ear ANC headphones, 30h battery.', '6999.99', 8),
    ('Webcam 1080p', 'Full HD webcam with privacy shutter.', '2199.00', 12),
    ('Portable SSD 1TB', 'USB 3.2 external solid state drive.', '7499.00', 6),
    ('Desk Lamp', 'LED desk lamp with three colour temperatures.', '999.00', 50),
    ('Monitor 27 inch', '27" QHD IPS monitor, 75Hz.', '18999.00', 4),
    ('Cable Organiser', 'Silicone cable management clips, pack of 10.', '249.00', 100),
    ('Laptop Sleeve 14 inch', 'Water resistant padded sleeve.', '899.00', 30),
    ('Bluetooth Speaker', 'Compact speaker, 12h playtime.', '3499.00', 18),
]


class Command(BaseCommand):
    help = 'Seed the database with sample products.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete all existing products before seeding.',
        )

    def handle(self, *args, **options):
        if options['flush']:
            deleted, _ = Product.objects.all().delete()
            self.stdout.write(f'Deleted {deleted} existing product(s).')

        created = 0
        for name, description, price, stock in SAMPLE_PRODUCTS:
            _, was_created = Product.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'price': Decimal(price),
                    'stock': stock,
                },
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(f'Seeded {created} new product(s).')
        )
