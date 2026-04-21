from django.urls import path

from .views import SearchView, health


urlpatterns = [
    path("health/", health, name="health"),
    path("search/", SearchView.as_view(), name="search"),
]
