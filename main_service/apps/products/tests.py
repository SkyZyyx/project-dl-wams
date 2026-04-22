from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TransactionTestCase

from .admin import ProductImageAdmin
from .models import Category, Product, ProductImage


def make_image_file(name: str = "product.png", size: tuple[int, int] = (128, 128), color=(120, 60, 30)):
    buffer = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class ProductImageSignalTests(TransactionTestCase):
    def setUp(self):
        self.factory = RequestFactory()
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

    @patch("apps.products.signals.index_product_image")
    @patch("apps.products.signals.delete_product_index")
    def test_product_image_delete_removes_vectors(self, mock_delete_product_index, mock_index_product_image):
        mock_index_product_image.return_value = {"qdrant_id": "1234"}
        image = ProductImage.objects.create(product=self.product, image=make_image_file(), is_primary=True)

        mock_delete_product_index.reset_mock()
        image.delete()

        mock_delete_product_index.assert_called_once_with(self.product.id)

    @patch("apps.products.signals.delete_product_index")
    def test_product_delete_removes_vectors(self, mock_delete_product_index):
        self.product.delete()

        mock_delete_product_index.assert_called()

    @patch("apps.products.signals.index_product_image")
    @patch("apps.products.admin.index_product_image")
    def test_admin_bulk_reindex_selected_images(self, mock_index_product_image, mock_signal_index_product_image):
        mock_signal_index_product_image.return_value = {"qdrant_id": "seed-123"}
        mock_index_product_image.return_value = {"qdrant_id": "bulk-123"}
        image = ProductImage.objects.create(product=self.product, image=make_image_file(), is_primary=True)
        image.indexed = False
        image.qdrant_id = None
        image.save(update_fields=["indexed", "qdrant_id"])

        admin = ProductImageAdmin(ProductImage, AdminSite())
        request = self.factory.get("/admin/")
        with patch.object(admin, "message_user") as mock_message_user:
            admin.reindex_selected_images(request, ProductImage.objects.filter(pk=image.pk))

        image.refresh_from_db()
        self.assertTrue(image.indexed)
        self.assertEqual(image.qdrant_id, "bulk-123")
        mock_index_product_image.assert_called_once()
        mock_message_user.assert_called_once()
