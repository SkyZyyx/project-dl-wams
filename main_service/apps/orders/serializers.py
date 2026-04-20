from django.db import transaction
from rest_framework import serializers

from apps.products.models import Product
from apps.products.serializers import CategorySerializer

from .models import Order, OrderItem


class OrderProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ("id", "name", "price", "category")


class OrderItemReadSerializer(serializers.ModelSerializer):
    product = OrderProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "quantity", "unit_price")


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "created_at", "updated_at", "items")


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemCreateSerializer(many=True, min_length=1)

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        user = validated_data.pop("user")
        order = Order.objects.create(user=user, **validated_data)
        for item_data in items_data:
            product = item_data["product"]
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item_data["quantity"],
                unit_price=product.price,
            )
        return order
