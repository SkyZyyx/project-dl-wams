from django.views.generic import TemplateView
from django.template.response import TemplateResponse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.auth_proxy import AuthServiceError, proxy_auth_post, proxy_auth_profile


def render_error_page(
    request,
    *,
    status_code: int,
    eyebrow: str,
    title: str,
    body: str,
    primary_label: str,
    primary_href: str,
    secondary_label: str | None = None,
    secondary_href: str | None = None,
    code_label: str | None = None,
):
    context = {
        "eyebrow": eyebrow,
        "title": title,
        "body": body,
        "primary_label": primary_label,
        "primary_href": primary_href,
        "secondary_label": secondary_label,
        "secondary_href": secondary_href,
        "status_code": status_code,
        "code_label": code_label or str(status_code),
    }
    return TemplateResponse(request, "users/error_page.html", context=context, status=status_code)


def bad_request_page(request, exception=None):
    return render_error_page(
        request,
        status_code=400,
        eyebrow="Bad request",
        title="That request could not be processed.",
        body="The page received something it could not understand. Go back to the storefront and try again.",
        primary_label="Back to home",
        primary_href="/",
        secondary_label="Open inventory",
        secondary_href="/",
    )


def permission_denied_page(request, exception=None):
    return render_error_page(
        request,
        status_code=403,
        eyebrow="Access denied",
        title="You do not have permission to open this area.",
        body="This section is reserved for seller or admin sessions. Use a permitted account or return to the storefront.",
        primary_label="Go to inventory",
        primary_href="/",
        secondary_label="Sign in",
        secondary_href="/auth/login/",
    )


def page_not_found(request, exception=None):
    return render_error_page(
        request,
        status_code=404,
        eyebrow="Not found",
        title="Nothing is parked here.",
        body="The address does not match a live page. Check the URL or return to the showroom.",
        primary_label="Back to home",
        primary_href="/",
        secondary_label="Open inventory",
        secondary_href="/",
    )


def server_error_page(request):
    return render_error_page(
        request,
        status_code=500,
        eyebrow="Server error",
        title="Something broke on our side.",
        body="The app hit an unexpected error. Try again in a moment or return to the storefront.",
        primary_label="Retry home",
        primary_href="/",
        secondary_label="Open inventory",
        secondary_href="/",
    )


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


class CarDetailPageView(TemplateView):
    template_name = "users/car_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["car_id"] = kwargs.get("pk")
        return context


class RegisterPageView(TemplateView):
    template_name = "users/register.html"


class LoginPageView(TemplateView):
    template_name = "users/login.html"


class ProfilePageView(TemplateView):
    template_name = "users/profile.html"


class SellerPageView(TemplateView):
    template_name = "users/seller.html"


class DashboardPageView(TemplateView):
    template_name = "users/dashboard.html"


class AccessDeniedPageView(TemplateView):
    template_name = "users/error_page.html"
    status_code = 403

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response.status_code = self.status_code
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_path = self.request.GET.get("next", "/")
        context.update(
            {
                "eyebrow": "Access denied",
                "title": "You do not have permission to open seller tools.",
                "body": "Use a seller or admin session to continue. Your current session does not allow listing creation.",
                "primary_label": "Go to inventory",
                "primary_href": "/",
                "secondary_label": "Sign in",
                "secondary_href": "/auth/login/",
                "status_code": 403,
                "code_label": "403",
                "next_path": next_path,
            }
        )
        return context
