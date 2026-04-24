from io import BytesIO
import json
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
        self.assertEqual(mock_get_embedder.call_args.args, ())
        mock_get_embedder.return_value.embed.assert_called_once_with(b"cropped-bytes")
        self.assertEqual(mock_upsert_vector.call_args.kwargs["payload"]["product_id"], 7)
        self.assertEqual(mock_upsert_vector.call_args.kwargs["payload"]["product_image_id"], 11)
        self.assertEqual(mock_upsert_vector.call_args.kwargs["payload"]["filename"], "test.png")
        self.assertNotIn("model_id", mock_upsert_vector.call_args.kwargs)

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
        self.assertNotIn("model_id", mock_upsert_vector.call_args.kwargs)

    @patch("apps.search.views.preprocess_image_bytes")
    @patch("apps.search.views.upsert_vector")
    @patch("apps.search.views.get_embedder")
    def test_index_endpoint_uses_default_model(self, mock_get_embedder, mock_upsert_vector, mock_preprocess_image_bytes):
        mock_get_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
        mock_preprocess_image_bytes.return_value = b"cropped-bytes"
        request = self.factory.post("/api/index/", {"product_id": 7, "image": make_image_file()}, format="multipart")

        response = IndexView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(mock_get_embedder.call_args.args, ())
        self.assertNotIn("model_id", mock_upsert_vector.call_args.kwargs)

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
        self.assertEqual(mock_get_embedder.call_args.args, ())
        mock_get_embedder.return_value.embed.assert_called_once_with(b"cropped-bytes")
        mock_is_query_vector_out_of_distribution.assert_called_once()
        mock_search_vectors.assert_called_once()
        self.assertEqual(mock_search_vectors.call_args.kwargs["limit"], 3)
        self.assertIsNone(mock_search_vectors.call_args.kwargs["score_threshold"])
        self.assertNotIn("model_id", mock_search_vectors.call_args.kwargs)

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
        request = mock_urlopen.call_args.args[0]
        self.assertIn("/collections/product_images_dinov2_base_pretrained/points/search", request.full_url)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["limit"], 3)
        self.assertEqual(payload["score_threshold"], 0.4)

    @patch("apps.search.services.qdrant.urllib_request.urlopen")
    @patch("apps.search.services.qdrant.ensure_collection")
    def test_search_vectors_omits_score_threshold_when_none(self, mock_ensure_collection, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"result":[]}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        from .services.qdrant import search_vectors

        search_vectors(vector=[0.1, 0.2, 0.3], limit=5)

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("score_threshold", payload)

    @patch("apps.search.services.qdrant.get_client")
    def test_collection_mean_vector_scans_qdrant_points(self, mock_get_client):
        mock_get_client.return_value.scroll.side_effect = [
            ([SimpleNamespace(vector=[1.0, 0.0])], "cursor-1"),
            ([SimpleNamespace(vector=[0.0, 1.0])], None),
        ]

        from .services.qdrant import clear_collection_mean_vector_cache, get_collection_mean_vector

        clear_collection_mean_vector_cache()
        mean_vector = get_collection_mean_vector()

        self.assertAlmostEqual(mean_vector[0], 0.7071, places=4)
        self.assertAlmostEqual(mean_vector[1], 0.7071, places=4)
        self.assertEqual(mock_get_client.return_value.scroll.call_count, 2)

    def test_model_registry_is_well_formed(self):
        from .services.model_registry import get_default_model_id, get_model_registry, get_model_spec

        registry = get_model_registry()

        self.assertEqual(get_default_model_id(), "dinov2_base_pretrained")
        self.assertEqual(set(registry.keys()), {
            "clip_vit_b32_pretrained",
            "dinov2_base_pretrained",
            "dinov2_base_transfer",
            "dinov2_base_finetuned",
        })
        self.assertEqual(len({spec.collection_name for spec in registry.values()}), len(registry))
        self.assertTrue(all(spec.vector_size > 0 for spec in registry.values()))
        self.assertEqual(get_model_spec().model_id, "dinov2_base_pretrained")

    def test_get_embedder_caches_per_model_family(self):
        from .services.embedder import get_embedder

        get_embedder.cache_clear()

        dino_embedder = get_embedder("dinov2_base_pretrained")
        same_dino_embedder = get_embedder("dinov2_base_pretrained")
        clip_embedder = get_embedder("clip_vit_b32_pretrained")

        self.assertIs(dino_embedder, same_dino_embedder)
        self.assertIsNot(dino_embedder, clip_embedder)
        self.assertEqual(dino_embedder.family, "dinov2")
        self.assertEqual(clip_embedder.family, "clip")
        self.assertEqual(dino_embedder.vector_size, 768)
        self.assertEqual(clip_embedder.vector_size, 512)

    @patch("apps.search.services.qdrant.get_client")
    def test_ensure_collection_uses_registry_collection_and_vector_size(self, mock_get_client):
        from .services.qdrant import ensure_collection

        mock_get_client.return_value.collection_exists.return_value = False

        ensure_collection("clip_vit_b32_pretrained")

        mock_get_client.return_value.create_collection.assert_called_once()
        self.assertEqual(
            mock_get_client.return_value.create_collection.call_args.kwargs["collection_name"],
            "product_images_clip_vit_b32_pretrained",
        )
        vector_params = mock_get_client.return_value.create_collection.call_args.kwargs["vectors_config"]
        self.assertEqual(vector_params.size, 512)

    @patch("apps.search.services.qdrant.get_client")
    def test_collection_mean_cache_is_isolated_per_model(self, mock_get_client):
        from .services.qdrant import clear_collection_mean_vector_cache, get_collection_mean_vector

        mock_get_client.return_value.scroll.side_effect = [
            ([SimpleNamespace(vector=[1.0, 0.0])], None),
            ([SimpleNamespace(vector=[0.0, 1.0])], None),
        ]

        clear_collection_mean_vector_cache("dinov2_base_pretrained")
        clear_collection_mean_vector_cache("clip_vit_b32_pretrained")
        dino_mean = get_collection_mean_vector("dinov2_base_pretrained")
        clip_mean = get_collection_mean_vector("clip_vit_b32_pretrained")

        self.assertEqual(mock_get_client.return_value.scroll.call_count, 2)
        self.assertNotEqual(dino_mean, clip_mean)

    @patch("apps.search.services.qdrant.ensure_collection")
    @patch("apps.search.services.qdrant.get_client")
    def test_upsert_vector_clears_only_affected_model_mean_cache(self, mock_get_client, mock_ensure_collection):
        from .services.qdrant import _COLLECTION_MEAN_CACHE, upsert_vector

        _COLLECTION_MEAN_CACHE.clear()
        _COLLECTION_MEAN_CACHE["dinov2_base_pretrained"] = [1.0]
        _COLLECTION_MEAN_CACHE["clip_vit_b32_pretrained"] = [2.0]

        upsert_vector(vector_id=1, vector=[0.1, 0.2], payload={"product_id": 1}, model_id="dinov2_base_pretrained")

        self.assertNotIn("dinov2_base_pretrained", _COLLECTION_MEAN_CACHE)
        self.assertIn("clip_vit_b32_pretrained", _COLLECTION_MEAN_CACHE)
        self.assertEqual(
            mock_get_client.return_value.upsert.call_args.kwargs["collection_name"],
            "product_images_dinov2_base_pretrained",
        )

    @patch("apps.search.services.qdrant.ensure_collection")
    @patch("apps.search.services.qdrant.get_client")
    def test_delete_by_product_id_clears_only_affected_model_mean_cache(self, mock_get_client, mock_ensure_collection):
        from .services.qdrant import _COLLECTION_MEAN_CACHE, delete_by_product_id

        _COLLECTION_MEAN_CACHE.clear()
        _COLLECTION_MEAN_CACHE["dinov2_base_pretrained"] = [1.0]
        _COLLECTION_MEAN_CACHE["clip_vit_b32_pretrained"] = [2.0]

        delete_by_product_id(7, model_id="clip_vit_b32_pretrained")

        self.assertNotIn("clip_vit_b32_pretrained", _COLLECTION_MEAN_CACHE)
        self.assertIn("dinov2_base_pretrained", _COLLECTION_MEAN_CACHE)
        self.assertEqual(
            mock_get_client.return_value.delete.call_args.kwargs["collection_name"],
            "product_images_clip_vit_b32_pretrained",
        )

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

    def test_gradcam_rejects_unsupported_model_family(self):
        from .services.visualization import generate_gradcam_overlay

        with self.assertRaisesMessage(ValueError, "gradcam is not supported"):
            generate_gradcam_overlay(make_image_file().read(), model_id="clip_vit_b32_pretrained")
