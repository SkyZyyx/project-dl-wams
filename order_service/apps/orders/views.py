from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Order
from .serializers import OrderCreateSerializer, OrderReadSerializer
from .services.order_read_policy import build_product_map


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
