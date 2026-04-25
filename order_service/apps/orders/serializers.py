from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import Order, OrderItem
from .services.catalog_client import CatalogServiceError, fetch_products_by_ids


class OrderCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class OrderProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    category = OrderCategorySerializer(allow_null=True, required=False)


class OrderItemReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product = serializers.SerializerMethodField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    def get_product(self, obj: OrderItem):
        live_map = self.context.get("product_map", {})
        payload = live_map.get(obj.product_id)
        if payload is not None:
            return payload

        category = None
        if obj.product_category_id is not None:
            category = {
                "id": obj.product_category_id,
                "name": obj.product_category_name,
                "slug": obj.product_category_slug,
            }

        return {
            "id": obj.product_id,
            "name": obj.product_name,
            "description": obj.product_description,
            "price": str(obj.unit_price),
            "category": category,
        }


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "user_id", "user_username", "user_email", "created_at", "updated_at", "items")


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemCreateSerializer(many=True, min_length=1)

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        user = validated_data.pop("user")
        user_id = getattr(user, "id", None)
        if user_id is None:
            raise serializers.ValidationError({"user": "Authenticated user id missing."})

        products = self._fetch_products(items_data)
        order = Order.objects.create(
            user_id=user_id,
            user_username=getattr(user, "username", ""),
            user_email=getattr(user, "email", ""),
        )

        for item_data in items_data:
            product = products[item_data["product_id"]]
            category = product.get("category") or {}
            OrderItem.objects.create(
                order=order,
                product_id=product["id"],
                product_name=product["name"],
                product_description=product.get("description", ""),
                product_category_id=category.get("id"),
                product_category_name=category.get("name", ""),
                product_category_slug=category.get("slug", ""),
                quantity=item_data["quantity"],
                unit_price=Decimal(str(product["price"])),
            )

        return order

    def _fetch_products(self, items_data):
        product_ids = []
        for item in items_data:
            product_id = item["product_id"]
            if product_id not in product_ids:
                product_ids.append(product_id)

        try:
            products_payload = fetch_products_by_ids(product_ids)
        except CatalogServiceError as exc:
            raise serializers.ValidationError({"items": str(exc)}) from exc

        products = {int(product["id"]): product for product in products_payload if product.get("id") is not None}
        missing = [product_id for product_id in product_ids if product_id not in products]
        if missing:
            raise serializers.ValidationError({"items": f"Unknown product ids: {missing}"})
        return products
