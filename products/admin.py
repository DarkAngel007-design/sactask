from django.contrib import admin

from .models import Order, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'price', 'stock', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'user', 'quantity', 'total_price', 'created_at')
    search_fields = ('product__name', 'user__username')
    list_filter = ('created_at',)
    readonly_fields = ('product', 'user', 'quantity', 'unit_price', 'total_price',
                       'idempotency_key', 'created_at')

    def has_change_permission(self, request, obj=None):
        return False
