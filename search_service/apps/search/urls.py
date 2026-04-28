from django.urls import path

from .views import DeleteIndexView, IndexView, SearchView


urlpatterns = [
    path("index/", IndexView.as_view(), name="index"),
    path("search/", SearchView.as_view(), name="search"),
    path("index/<int:product_id>/", DeleteIndexView.as_view(), name="index-delete"),
]
