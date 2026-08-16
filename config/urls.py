"""URL configuration for the project.

Everything under /api/ is delegated to the products app.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('products.urls')),
]
