from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.conf.urls.static import static

from apps.users.views import LandingPageView


urlpatterns = [
    path("", LandingPageView.as_view(), name="home"),
    path("auth/", include("apps.users.ui_urls")),
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.users.urls")),
    path("api/", include("apps.products.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
