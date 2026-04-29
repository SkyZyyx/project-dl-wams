from django.contrib import admin
from django.urls import include, path

from apps.search.admin_views import search_operations_view


urlpatterns = [
    path("admin/ops/", admin.site.admin_view(search_operations_view), name="search-admin-ops"),
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.search.urls")),
]
