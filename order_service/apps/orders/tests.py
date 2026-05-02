from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .models import Order, OrderItem
from .serializers import OrderReadSerializer
from .services.catalog_client import CatalogServiceError
from .views import OrderDetailView, OrderListCreateView


class _FakeUser:
    def __init__(self, user_id=1, role="client", email=None):
        self.id = user_id
        self.is_authenticated = True
        self.token = {"role": role}
        self.role = role
        self.email = email


class OrderReadPolicyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _make_order(self):
        order = Order.objects.create(user_id=1, user_username="alice", user_email="alice@example.com")
        OrderItem.objects.create(
            order=order,
            product_id=11,
            product_name="Snapshot Shoe",
            product_description="Snapshot description",
            product_category_id=7,
            product_category_name="Shoes",
            product_category_slug="shoes",
            quantity=2,
            unit_price=Decimal("19.99"),
        )
        return order

    @patch("apps.orders.services.order_read_policy.fetch_products_by_ids")
    def test_list_view_hydrates_product_map(self, mock_fetch_products_by_ids):
        order = self._make_order()
        mock_fetch_products_by_ids.return_value = [
            {"id": 11, "name": "Live Shoe", "description": "Live", "price": "29.99", "category": None}
        ]
        user = _FakeUser()
        request = self.factory.get("/api/orders/")
        force_authenticate(request, user=user)

        response = OrderListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["items"][0]["product"]["name"], "Live Shoe")
        mock_fetch_products_by_ids.assert_called_once_with([11])

    @patch("apps.orders.services.order_read_policy.fetch_products_by_ids")
    def test_detail_view_silently_falls_back_to_snapshot_data_when_catalog_is_down(self, mock_fetch_products_by_ids):
        order = self._make_order()
        mock_fetch_products_by_ids.side_effect = CatalogServiceError("boom")
        user = _FakeUser()
        request = self.factory.get(f"/api/orders/{order.pk}/")
        force_authenticate(request, user=user)

        response = OrderDetailView.as_view()(request, pk=order.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["product"]["name"], "Snapshot Shoe")
        self.assertEqual(response.data["items"][0]["product"]["category"]["slug"], "shoes")

    def test_serializer_uses_snapshot_payload_when_product_map_is_missing(self):
        order = self._make_order()

        data = OrderReadSerializer(order).data

        self.assertEqual(data["items"][0]["product"]["name"], "Snapshot Shoe")
        self.assertEqual(data["items"][0]["product"]["price"], "19.99")

    @patch("apps.orders.serializers.fetch_products_by_ids")
    def test_client_can_create_order(self, mock_fetch_products_by_ids):
        mock_fetch_products_by_ids.return_value = [
            {"id": 11, "name": "Live Shoe", "description": "Live", "price": "29.99", "category": None}
        ]
        user = _FakeUser(role="client")
        request = self.factory.post("/api/orders/", {"items": [{"product_id": 11, "quantity": 1}]}, format="json")
        force_authenticate(request, user=user)

        response = OrderListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.count(), 1)

    @patch("apps.orders.serializers.fetch_products_by_ids")
    def test_seller_cannot_create_order(self, mock_fetch_products_by_ids):
        user = _FakeUser(role="seller")
        request = self.factory.post("/api/orders/", {"items": [{"product_id": 11, "quantity": 1}]}, format="json")
        force_authenticate(request, user=user)

        response = OrderListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Only client or admin accounts can place orders.")
        mock_fetch_products_by_ids.assert_not_called()
        self.assertEqual(Order.objects.count(), 0)

    @patch("apps.orders.serializers.fetch_products_by_ids")
    def test_admin_can_create_order(self, mock_fetch_products_by_ids):
        mock_fetch_products_by_ids.return_value = [
            {"id": 11, "name": "Live Shoe", "description": "Live", "price": "29.99", "category": None}
        ]
        user = _FakeUser(role="admin")
        request = self.factory.post("/api/orders/", {"items": [{"product_id": 11, "quantity": 1}]}, format="json")
        force_authenticate(request, user=user)

        response = OrderListCreateView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.count(), 1)
