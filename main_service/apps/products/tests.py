from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import Category, Product, ProductImage


def make_image_file(name: str = "product.png", size: tuple[int, int] = (128, 128), color=(120, 60, 30)):
    buffer = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ProductImageSignalTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Clothing")
        self.product = Product.objects.create(name="Shirt", description="", price="12.00", category=category)

    @patch("apps.products.signals.index_product_image")
    def test_product_image_create_auto_indexes(self, mock_index_product_image):
        mock_index_product_image.return_value = {"qdrant_id": "1234"}

        image = ProductImage.objects.create(product=self.product, image=make_image_file(), is_primary=True)

        image.refresh_from_db()
        self.assertTrue(image.indexed)
        self.assertEqual(str(image.qdrant_id), "1234")
        mock_index_product_image.assert_called_once()

    @patch("apps.products.signals.delete_product_index")
    def test_product_image_delete_removes_vectors(self, mock_delete_product_index):
        image = ProductImage.objects.create(product=self.product, image=make_image_file(), is_primary=True)

        mock_delete_product_index.reset_mock()
        image.delete()

        mock_delete_product_index.assert_called_once_with(self.product.id)

    @patch("apps.products.signals.delete_product_index")
    def test_product_delete_removes_vectors(self, mock_delete_product_index):
        self.product.delete()

        self.assertGreaterEqual(mock_delete_product_index.call_count, 1)
        self.assertTrue(any(call.args[0] == self.product.id for call in mock_delete_product_index.call_args_list))
