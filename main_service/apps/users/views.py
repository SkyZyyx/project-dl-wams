from django.views.generic import TemplateView
from rest_framework import generics, permissions

from .serializers import RegistrationSerializer, UserProfileSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LandingPageView(TemplateView):
    template_name = "users/index.html"


class RegisterPageView(TemplateView):
    template_name = "users/register.html"


class LoginPageView(TemplateView):
    template_name = "users/login.html"


class ProfilePageView(TemplateView):
    template_name = "users/profile.html"
