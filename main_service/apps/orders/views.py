from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Order
from .serializers import OrderCreateSerializer, OrderReadSerializer


class OrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrderCreateSerializer
        return OrderReadSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items__product", "items__product__category")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(user=request.user)
        headers = self.get_success_headers(serializer.data)
        output = OrderReadSerializer(order, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderReadSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items__product", "items__product__category")
