from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image
from PIL import ImageDraw
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from .services.preprocess import preprocess_image_bytes
from .services.quality import validate_image_quality
from .views import DeleteIndexView, GradCamView, IndexView, SearchView


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


def make_object_image_file(name: str = "object.png"):
    buffer = BytesIO()
    image = Image.new("RGB", (160, 160), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 40, 110, 120), fill=(30, 80, 180))
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

    @patch("apps.search.views.preprocess_image_bytes")
    @patch("apps.search.views.upsert_vector")
    @patch("apps.search.views.get_embedder")
    def test_index_endpoint_indexes_image(self, mock_get_embedder, mock_upsert_vector, mock_preprocess_image_bytes):
        mock_get_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mock_preprocess_image_bytes.return_value = b"cropped-bytes"
        request = self.factory.post(
            "/api/index/",
            {"product_id": 7, "product_image_id": 11, "image": make_image_file()},
            format="multipart",
        )

        response = IndexView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "indexed")
        mock_preprocess_image_bytes.assert_called_once()
        mock_upsert_vector.assert_called_once()
        mock_get_embedder.return_value.embed.assert_called_once_with(b"cropped-bytes")

    @patch("apps.search.views.preprocess_image_bytes")
    @patch("apps.search.views.upsert_vector")
    @patch("apps.search.views.get_embedder")
    def test_index_endpoint_uses_numeric_point_id(self, mock_get_embedder, mock_upsert_vector, mock_preprocess_image_bytes):
        mock_get_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mock_preprocess_image_bytes.return_value = b"cropped-bytes"
        request = self.factory.post(
            "/api/index/",
            {"product_id": 7, "product_image_id": 11, "image": make_image_file()},
            format="multipart",
        )

        response = IndexView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(mock_upsert_vector.call_args.kwargs["vector_id"], 11)

    @patch("apps.search.views.preprocess_image_bytes")
    @patch("apps.search.views.search_vectors")
    @patch("apps.search.views.is_query_vector_out_of_distribution")
    @patch("apps.search.views.get_embedder")
    def test_search_endpoint_returns_matches(
        self,
        mock_get_embedder,
        mock_is_query_vector_out_of_distribution,
        mock_search_vectors,
        mock_preprocess_image_bytes,
    ):
        mock_get_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mock_preprocess_image_bytes.return_value = b"cropped-bytes"
        mock_is_query_vector_out_of_distribution.return_value = False
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
        mock_preprocess_image_bytes.assert_called_once()
        mock_get_embedder.return_value.embed.assert_called_once_with(b"cropped-bytes")
        mock_is_query_vector_out_of_distribution.assert_called_once()
        mock_search_vectors.assert_called_once()

    @patch("apps.search.views.preprocess_image_bytes")
    @patch("apps.search.views.search_vectors")
    @patch("apps.search.views.is_query_vector_out_of_distribution")
    @patch("apps.search.views.get_embedder")
    def test_search_endpoint_rejects_low_scoring_top_hit(
        self,
        mock_get_embedder,
        mock_is_query_vector_out_of_distribution,
        mock_search_vectors,
        mock_preprocess_image_bytes,
    ):
        mock_get_embedder.return_value.embed.return_value = [0.2, 0.3, 0.4]
        mock_preprocess_image_bytes.return_value = b"cropped-bytes"
        mock_is_query_vector_out_of_distribution.return_value = False
        mock_search_vectors.return_value = [
            SimpleNamespace(id="off", score=0.31, payload={"product_id": 7, "product_image_id": 11})
        ]
        request = self.factory.post(
            "/api/search/",
            {"image": make_image_file(), "limit": 3},
            format="multipart",
        )

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "no similar products found")
        self.assertEqual(response.data["matches"], [])
        mock_preprocess_image_bytes.assert_called_once()
        mock_get_embedder.return_value.embed.assert_called_once_with(b"cropped-bytes")
        mock_is_query_vector_out_of_distribution.assert_called_once()
        mock_search_vectors.assert_called_once()

    @patch("apps.search.views.preprocess_image_bytes")
    @patch("apps.search.views.search_vectors")
    @patch("apps.search.views.is_query_vector_out_of_distribution")
    @patch("apps.search.views.get_embedder")
    def test_search_endpoint_rejects_ood_query(
        self,
        mock_get_embedder,
        mock_is_query_vector_out_of_distribution,
        mock_search_vectors,
        mock_preprocess_image_bytes,
    ):
        mock_get_embedder.return_value.embed.return_value = [1.0, 0.0, 0.0]
        mock_preprocess_image_bytes.return_value = b"cropped-bytes"
        mock_is_query_vector_out_of_distribution.return_value = True
        request = self.factory.post(
            "/api/search/",
            {"image": make_image_file(), "limit": 3},
            format="multipart",
        )

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "no similar products found")
        self.assertEqual(response.data["matches"], [])
        mock_preprocess_image_bytes.assert_called_once()
        mock_get_embedder.return_value.embed.assert_called_once_with(b"cropped-bytes")
        mock_is_query_vector_out_of_distribution.assert_called_once()
        mock_search_vectors.assert_not_called()

    def test_preprocess_image_bytes_crops_foreground_object(self):
        image = make_object_image_file()

        processed = preprocess_image_bytes(image.read())

        result = Image.open(BytesIO(processed))
        self.assertLess(result.width, 160)
        self.assertLess(result.height, 160)

    def test_preprocess_image_bytes_falls_back_when_no_object_detected(self):
        buffer = BytesIO()
        Image.new("RGB", (128, 128), color=(240, 240, 240)).save(buffer, format="PNG")

        original = buffer.getvalue()
        processed = preprocess_image_bytes(original)

        self.assertEqual(processed, original)

    @override_settings(SEARCH_PREPROCESS_USE_REMBG=True)
    @patch("apps.search.services.preprocess.rembg_remove")
    def test_preprocess_image_bytes_can_use_rembg_mask(self, mock_rembg_remove):
        buffer = BytesIO()
        image = Image.new("RGBA", (160, 160), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((45, 35, 115, 125), fill=(10, 20, 30, 255))
        image.save(buffer, format="PNG")
        mock_rembg_remove.return_value = buffer.getvalue()

        processed = preprocess_image_bytes(b"ignored")

        result = Image.open(BytesIO(processed))
        self.assertLess(result.width, 160)
        self.assertLess(result.height, 160)

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

    @patch("apps.search.services.qdrant.get_client")
    def test_collection_mean_vector_scans_qdrant_points(self, mock_get_client):
        mock_get_client.return_value.scroll.side_effect = [
            ([SimpleNamespace(vector=[1.0, 0.0])], "cursor-1"),
            ([SimpleNamespace(vector=[0.0, 1.0])], None),
        ]

        from .services.qdrant import get_collection_mean_vector

        get_collection_mean_vector.cache_clear()
        mean_vector = get_collection_mean_vector()

        self.assertAlmostEqual(mean_vector[0], 0.7071, places=4)
        self.assertAlmostEqual(mean_vector[1], 0.7071, places=4)
        self.assertEqual(mock_get_client.return_value.scroll.call_count, 2)

    @patch("apps.search.views.delete_by_product_id")
    def test_delete_index_endpoint_deletes_product_vectors(self, mock_delete_by_product_id):
        request = self.factory.delete("/api/index/7/")

        response = DeleteIndexView.as_view()(request, product_id=7)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product_id"], 7)
        mock_delete_by_product_id.assert_called_once_with(7)

    @patch("apps.search.views.generate_gradcam_overlay")
    def test_gradcam_endpoint_returns_overlay(self, mock_generate_gradcam_overlay):
        mock_generate_gradcam_overlay.return_value = {"overlay_b64": "abc", "width": 128, "height": 128}
        request = self.factory.post("/api/gradcam/", {"image": make_image_file()}, format="multipart")

        response = GradCamView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["overlay_b64"], "abc")
        mock_generate_gradcam_overlay.assert_called_once()
