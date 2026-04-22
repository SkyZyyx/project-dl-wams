from django.urls import path

from .views import DeleteIndexView, GradCamView, IndexView, SearchView


urlpatterns = [
    path("index/", IndexView.as_view(), name="index"),
    path("search/", SearchView.as_view(), name="search"),
    path("gradcam/", GradCamView.as_view(), name="gradcam"),
    path("index/<int:product_id>/", DeleteIndexView.as_view(), name="index-delete"),
]
