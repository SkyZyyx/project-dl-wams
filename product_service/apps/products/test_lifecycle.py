from __future__ import annotations

import tempfile
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from .lifecycle import index_product_image_record, refresh_product_image_vectors
from .models import Category, Product, ProductImage
from .services.search_proxy import SearchServiceError


def _make_uploaded_image(name: str = "image.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color="white").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class ProductImageLifecycleTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_root = tempfile.TemporaryDirectory()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root.name)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        cls._media_root.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.category = Category.objects.create(name="Cars", slug="cars")
        self.product = Product.objects.create(
            name="Roadster",
            description="",
            price="100.00",
            category=self.category,
            seller_username="seller-1",
        )

    def test_index_product_image_record_persists_search_identifier(self):
        image = ProductImage.objects.create(product=self.product, image=_make_uploaded_image())

        with patch("apps.products.lifecycle.index_product_image", return_value={"qdrant_id": "q-123"}) as mocked:
            index_product_image_record(image)

        image.refresh_from_db()
        self.assertTrue(image.indexed)
        self.assertEqual(image.qdrant_id, "q-123")
        mocked.assert_called_once()

    def test_refresh_product_image_vectors_reindexes_remaining_images_after_delete(self):
        image_one = ProductImage.objects.create(product=self.product, image=_make_uploaded_image("one.jpg"))
        image_two = ProductImage.objects.create(product=self.product, image=_make_uploaded_image("two.jpg"))

        def _response(*, product_image_id, **kwargs):
            return {"qdrant_id": f"q-{product_image_id}"}

        with patch("apps.products.lifecycle.delete_product_index") as delete_mock, patch(
            "apps.products.lifecycle.index_product_image", side_effect=_response
        ) as index_mock:
            refresh_product_image_vectors(self.product.pk)

        delete_mock.assert_called_once_with(self.product.pk)
        self.assertEqual(index_mock.call_count, 2)
        image_one.refresh_from_db()
        image_two.refresh_from_db()
        self.assertEqual(image_one.qdrant_id, f"q-{image_one.pk}")
        self.assertEqual(image_two.qdrant_id, f"q-{image_two.pk}")
        self.assertTrue(image_one.indexed)
        self.assertTrue(image_two.indexed)

    def test_refresh_product_image_vectors_logs_and_skips_when_search_service_unavailable(self):
        image = ProductImage.objects.create(product=self.product, image=_make_uploaded_image())

        with patch("apps.products.lifecycle.delete_product_index", side_effect=SearchServiceError("down")), patch(
            "apps.products.lifecycle.logger.warning"
        ) as warning_mock, patch("apps.products.lifecycle.index_product_image") as index_mock:
            refresh_product_image_vectors(self.product.pk)

        warning_mock.assert_called_once()
        index_mock.assert_not_called()
        image.refresh_from_db()
        self.assertFalse(image.indexed)
