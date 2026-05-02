from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Order
from .serializers import OrderCreateSerializer, OrderReadSerializer
from .services.order_read_policy import build_product_map


def _request_role(request) -> str:
    token = getattr(request.user, "token", None)
    if token is not None:
        role = token.get("role")
        if isinstance(role, str):
            return role.strip().lower()

    role = getattr(request.user, "role", "")
    if isinstance(role, str):
        return role.strip().lower()
    return ""


def _can_manage_orders(request) -> bool:
    return _request_role(request) in {"client", "admin"}


class OrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrderCreateSerializer
        return OrderReadSerializer

    def get_queryset(self):
        return Order.objects.filter(user_id=self.request.user.id).prefetch_related("items")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["product_map"] = build_product_map(self.get_queryset())
        return context

    def create(self, request, *args, **kwargs):
        if not _can_manage_orders(request):
            return Response(
                {"detail": "Only client or admin accounts can place orders."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(user=request.user)
        output = OrderReadSerializer(order, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderReadSerializer

    def get_queryset(self):
        return Order.objects.filter(user_id=self.request.user.id).prefetch_related("items")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["product_map"] = build_product_map(self.get_queryset())
        return context
