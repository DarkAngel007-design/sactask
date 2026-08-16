from rest_framework.routers import DefaultRouter

from .views import ProductViewSet

# The router inspects the viewset and generates one URL pattern per action,
# including the extra @action-decorated `purchase` endpoint.
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = router.urls
