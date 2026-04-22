from django.urls import path

from .views import DemoPageView, GradCamView, SearchView, health


urlpatterns = [
    path("health/", health, name="health"),
    path("demo/", DemoPageView.as_view(), name="demo"),
    path("search/", SearchView.as_view(), name="search"),
    path("gradcam/", GradCamView.as_view(), name="gradcam"),
]
