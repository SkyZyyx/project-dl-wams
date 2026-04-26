from django.urls import path

from .views import LoginView, ProfileView, RegisterView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="token_obtain_pair"),
    path("profile/", ProfileView.as_view(), name="profile"),
]
