from django.urls import path

from .views import AccessDeniedPageView, DashboardPageView, LoginPageView, ProfilePageView, RegisterPageView, SellerPageView


urlpatterns = [
    path("register/", RegisterPageView.as_view(), name="register_page"),
    path("login/", LoginPageView.as_view(), name="login_page"),
    path("profile/", ProfilePageView.as_view(), name="profile_page"),
    path("access-denied/", AccessDeniedPageView.as_view(), name="access_denied_page"),
    path("dashboard/", DashboardPageView.as_view(), name="dashboard_page"),
    path("seller/", SellerPageView.as_view(), name="seller_page"),
]
