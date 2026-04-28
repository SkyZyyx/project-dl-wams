from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.conf.urls.static import static

from apps.core.views import DemoPageView
from apps.users.views import CarDetailPageView, LandingPageView, bad_request_page, page_not_found, permission_denied_page, server_error_page


urlpatterns = [
    path("", LandingPageView.as_view(), name="home"),
    path("cars/<int:pk>/", CarDetailPageView.as_view(), name="car-detail"),
    path("demo/", DemoPageView.as_view(), name="demo"),
    path("auth/", include("apps.users.ui_urls")),
    path("api/auth/", include("apps.users.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = bad_request_page
handler403 = permission_denied_page
handler404 = page_not_found
handler500 = server_error_page
