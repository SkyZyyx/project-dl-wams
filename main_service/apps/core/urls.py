from django.urls import path

from .views import DemoPageView, OrderDetailProxyView, OrderListProxyView, ProductCategoryView, ProductDetailProxyView, ProductImageUploadView, ProductListView, SearchView, health


urlpatterns = [
    path("health/", health, name="health"),
    path("demo/", DemoPageView.as_view(), name="demo"),
    path("products/categories/", ProductCategoryView.as_view(), name="product-categories"),
    path("products/", ProductListView.as_view(), name="products"),
    path("products/<int:pk>/", ProductDetailProxyView.as_view(), name="product-detail"),
    path("products/<int:pk>/images/", ProductImageUploadView.as_view(), name="product-image-upload"),
    path("orders/", OrderListProxyView.as_view(), name="orders"),
    path("orders/<int:pk>/", OrderDetailProxyView.as_view(), name="order-detail"),
    path("search/", SearchView.as_view(), name="search"),
]
