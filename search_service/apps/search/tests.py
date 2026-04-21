from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
from PIL import ImageDraw
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .services.quality import validate_image_quality
from .views import DeleteIndexView, IndexView, SearchView


def make_image_file(name: str = "test.png", size: tuple[int, int] = (128, 128), color=(120, 60, 30)):
    buffer = BytesIO()
    image = Image.new("RGB", size, color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    block = 16
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            fill = color if (x // block + y // block) % 2 == 0 else (255, 255, 255)
            draw.rectangle((x, y, min(x + block - 1, size[0] - 1), min(y + block - 1, size[1] - 1)), fill=fill)
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class SearchServiceSmokeTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_validate_image_quality_rejects_too_small_image(self):
        image = make_image_file(size=(32, 32))
        ok, reason = validate_image_quality(image.read())

        self.assertFalse(ok)
        self.assertEqual(reason, "image too small")

    @patch("apps.search.views.upsert_vector")
    @patch("apps.search.views.get_embedder")
    def test_index_endpoint_indexes_image(self, mock_get_embedder, mock_upsert_vector):
        mock_get_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        request = self.factory.post(
            "/api/index/",
            {"product_id": 7, "product_image_id": 11, "image": make_image_file()},
            format="multipart",
        )

        response = IndexView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "indexed")
        mock_upsert_vector.assert_called_once()

    @patch("apps.search.views.upsert_vector")
    @patch("apps.search.views.get_embedder")
    def test_index_endpoint_uses_numeric_point_id(self, mock_get_embedder, mock_upsert_vector):
        mock_get_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        request = self.factory.post(
            "/api/index/",
            {"product_id": 7, "product_image_id": 11, "image": make_image_file()},
            format="multipart",
        )

        response = IndexView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(mock_upsert_vector.call_args.kwargs["vector_id"], 11)

    @patch("apps.search.views.search_vectors")
    @patch("apps.search.views.get_embedder")
    def test_search_endpoint_returns_matches(self, mock_get_embedder, mock_search_vectors):
        mock_get_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mock_search_vectors.return_value = [
            SimpleNamespace(id="abc", score=0.91, payload={"product_id": 7, "product_image_id": 11})
        ]
        request = self.factory.post(
            "/api/search/",
            {"image": make_image_file(), "limit": 3},
            format="multipart",
        )

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["matches"][0]["product_id"], 7)
        self.assertEqual(response.data["matches"][0]["qdrant_id"], "abc")
        mock_search_vectors.assert_called_once()

    @patch("apps.search.services.qdrant.urllib_request.urlopen")
    @patch("apps.search.services.qdrant.ensure_collection")
    def test_search_vectors_uses_qdrant_http_search(self, mock_ensure_collection, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result":[{"id":"abc","score":0.91,"payload":{}}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        from .services.qdrant import search_vectors

        results = search_vectors(vector=[0.1, 0.2, 0.3], limit=3, score_threshold=0.4)

        self.assertEqual(results[0].id, "abc")
        self.assertEqual(results[0].score, 0.91)
        mock_urlopen.assert_called_once()

    @patch("apps.search.views.delete_by_product_id")
    def test_delete_index_endpoint_deletes_product_vectors(self, mock_delete_by_product_id):
        request = self.factory.delete("/api/index/7/")

        response = DeleteIndexView.as_view()(request, product_id=7)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product_id"], 7)
        mock_delete_by_product_id.assert_called_once_with(7)
