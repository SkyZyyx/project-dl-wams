from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import Category, Product
from .permissions import ProductOwnerPermission, SellerWritePermission
from .serializers import ProductSerializer
from .views import ProductDetailView


class _FakeUser:
    def __init__(self, *, username="", role=None, token=None, is_authenticated=True):
        self.username = username
        self.role = role
        self.token = token
        self.is_authenticated = is_authenticated


class ProductPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_write_denied_for_client_role(self):
        request = self.factory.post("/api/products/", {"name": "x"}, format="json")
        request.user = _FakeUser(token={"role": "client", "username": "client-1"})

        allowed = SellerWritePermission().has_permission(request, None)

        self.assertFalse(allowed)

    def test_write_allowed_for_admin_role(self):
        request = self.factory.post("/api/products/", {"name": "x"}, format="json")
        request.user = _FakeUser(token={"role": "admin", "username": "admin-1"})

        allowed = SellerWritePermission().has_permission(request, None)

        self.assertTrue(allowed)

    def test_owner_check_uses_token_username_fallback(self):
        category = Category.objects.create(name="Cars", slug="cars")
        product = Product.objects.create(
            name="Car",
            description="d",
            price=Decimal("100.00"),
            category=category,
            seller_username="seller-a",
        )
        request = self.factory.patch("/api/products/1/", {"name": "updated"}, format="json")
        request.user = _FakeUser(role="seller", token={"role": "seller", "username": "seller-a"})

        allowed = ProductOwnerPermission().has_object_permission(request, None, product)

        self.assertTrue(allowed)

    def test_owner_check_allows_admin_override(self):
        category = Category.objects.create(name="Cars", slug="cars")
        product = Product.objects.create(
            name="Car",
            description="d",
            price=Decimal("100.00"),
            category=category,
            seller_username="seller-a",
        )
        request = self.factory.patch("/api/products/1/", {"name": "updated"}, format="json")
        request.user = _FakeUser(role="admin", token={"role": "admin", "username": "admin-1"})

        allowed = ProductOwnerPermission().has_object_permission(request, None, product)

        self.assertTrue(allowed)

    def test_owner_can_update_product(self):
        category = Category.objects.create(name="Cars", slug="cars")
        product = Product.objects.create(
            name="Car",
            description="d",
            price=Decimal("100.00"),
            category=category,
            seller_username="seller-a",
        )
        request = self.factory.patch(
            f"/api/products/{product.pk}/",
            {"name": "Updated car"},
            format="json",
        )
        request.user = _FakeUser(role="seller", token={"role": "seller", "username": "seller-a"})

        response = ProductDetailView.as_view()(request, pk=product.pk)

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.name, "Updated car")

    def test_non_owner_cannot_update_product(self):
        category = Category.objects.create(name="Cars", slug="cars")
        product = Product.objects.create(
            name="Car",
            description="d",
            price=Decimal("100.00"),
            category=category,
            seller_username="seller-a",
        )
        request = self.factory.patch(
            f"/api/products/{product.pk}/",
            {"name": "Updated car"},
            format="json",
        )
        request.user = _FakeUser(role="seller", token={"role": "seller", "username": "seller-b"})

        response = ProductDetailView.as_view()(request, pk=product.pk)

        self.assertEqual(response.status_code, 403)
        product.refresh_from_db()
        self.assertEqual(product.name, "Car")


class ProductSerializerTests(TestCase):
    def test_create_sets_seller_from_token_username_when_user_username_empty(self):
        request = APIRequestFactory().post("/api/products/", {"name": "x"}, format="json")
        request.user = _FakeUser(role="seller", username="", token={"role": "seller", "username": "seller-token"})
        serializer = ProductSerializer(context={"request": request})

        product = serializer.create(
            {
                "name": "Land Rover",
                "description": "desc",
                "price": Decimal("999.99"),
                "image_files": [],
            }
        )

        self.assertEqual(product.seller_username, "seller-token")
        self.assertIsNone(product.category)
