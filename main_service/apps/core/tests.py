from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.products.models import Category, Product
from .views import SearchView


def make_image_file(name: str = "query.png", size: tuple[int, int] = (128, 128), color=(120, 60, 30)):
    buffer = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class SearchProxyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        category = Category.objects.create(name="Shoes")
        self.product_low = Product.objects.create(name="Low", description="", price="10.00", category=category)
        self.product_high = Product.objects.create(name="High", description="", price="20.00", category=category)

    @patch("apps.core.views.proxy_search_image")
    def test_search_proxy_hydrates_and_sorts_matches(self, mock_proxy_search_image):
        mock_proxy_search_image.return_value = {
            "matches": [
                {"product_id": self.product_low.id, "product_image_id": 7, "qdrant_id": "a", "score": 0.81},
                {"product_id": self.product_high.id, "product_image_id": 8, "qdrant_id": "b", "score": 0.97},
            ]
        }
        request = self.factory.post("/api/search/", {"image": make_image_file()}, format="multipart")

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["matches"]], [self.product_high.id, self.product_low.id])
        self.assertEqual(response.data["matches"][0]["score"], 0.97)
        self.assertEqual(response.data["matches"][1]["score"], 0.81)
        mock_proxy_search_image.assert_called_once()
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["image_name"], "query.png")
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["content_type"], "image/png")
        self.assertTrue(mock_proxy_search_image.call_args.kwargs["image_bytes"])
