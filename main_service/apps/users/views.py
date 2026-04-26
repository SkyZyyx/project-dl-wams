from django.views.generic import TemplateView
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.auth_proxy import AuthServiceError, proxy_auth_post, proxy_auth_profile


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            payload = proxy_auth_post("register/", dict(request.data))
            return Response(payload, status=status.HTTP_201_CREATED)
        except AuthServiceError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            payload = proxy_auth_post("login/", dict(request.data))
            return Response(payload, status=status.HTTP_200_OK)
        except AuthServiceError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)


class ProfileView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        authorization = request.headers.get("Authorization", "")
        token = authorization.replace("Bearer ", "", 1).strip()
        if not token:
            return Response({"detail": "Authorization header missing Bearer token."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = proxy_auth_profile(token)
            return Response(payload, status=status.HTTP_200_OK)
        except AuthServiceError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)


class LandingPageView(TemplateView):
    template_name = "users/index.html"


class RegisterPageView(TemplateView):
    template_name = "users/register.html"


class LoginPageView(TemplateView):
    template_name = "users/login.html"


class ProfilePageView(TemplateView):
    template_name = "users/profile.html"


class SellerPageView(TemplateView):
    template_name = "users/seller.html"
