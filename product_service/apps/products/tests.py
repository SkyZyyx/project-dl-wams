from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import Category, Product
from .permissions import ProductOwnerOrAdminPermission, SellerOrAdminWritePermission
from .serializers import ProductSerializer


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

        allowed = SellerOrAdminWritePermission().has_permission(request, None)

        self.assertFalse(allowed)

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

        allowed = ProductOwnerOrAdminPermission().has_object_permission(request, None, product)

        self.assertTrue(allowed)


class ProductSerializerTests(TestCase):
    def test_create_sets_seller_from_token_username_when_user_username_empty(self):
        category = Category.objects.create(name="SUV", slug="suv")
        request = APIRequestFactory().post("/api/products/", {"name": "x"}, format="json")
        request.user = _FakeUser(role="seller", username="", token={"role": "seller", "username": "seller-token"})
        serializer = ProductSerializer(context={"request": request})

        product = serializer.create(
            {
                "name": "Land Rover",
                "description": "desc",
                "price": Decimal("999.99"),
                "category": category,
                "image_files": [],
            }
        )

        self.assertEqual(product.seller_username, "seller-token")
