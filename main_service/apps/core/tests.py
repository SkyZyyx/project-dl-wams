from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory

from apps.core.views import DemoPageView
from apps.core.services.search_hydration import hydrate_search_matches
from apps.core.services.catalog_proxy import CatalogServiceError
from apps.users.views import (
    AccessDeniedPageView,
    CarDetailPageView,
    LandingPageView,
    LoginPageView,
    ProfilePageView,
    RegisterPageView,
    bad_request_page,
    page_not_found,
    permission_denied_page,
    server_error_page,
)
from .permissions import SellerWritePermission
from .views import SearchView


def make_image_file(name: str = "query.png", size: tuple[int, int] = (128, 128), color=(120, 60, 30)):
    buffer = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class SearchProxyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_search_hydration_dedupes_and_sorts_matches(self):
        def fetch_products_by_ids(product_ids):
            self.assertEqual(product_ids, [11, 22])
            return [
                {
                    "id": 11,
                    "name": "Low",
                    "price": "10.00",
                    "category": {"id": 1, "name": "Shoes", "slug": "shoes"},
                },
                {
                    "id": 22,
                    "name": "High",
                    "price": "20.00",
                    "category": {"id": 1, "name": "Shoes", "slug": "shoes"},
                },
            ]

        matches, detail = hydrate_search_matches(
            {
                "matches": [
                    {"product_id": 11, "product_image_id": 7, "qdrant_id": "a", "score": 0.81},
                    {"product_id": 22, "product_image_id": 8, "qdrant_id": "b", "score": 0.97},
                    {"product_id": 11, "product_image_id": 9, "qdrant_id": "c", "score": 0.92},
                ]
            },
            fetch_products_by_ids=fetch_products_by_ids,
        )

        self.assertIsNone(detail)
        self.assertEqual([item["id"] for item in matches], [22, 11])
        self.assertEqual(matches[0]["score"], 0.97)
        self.assertEqual(matches[1]["score"], 0.92)
        self.assertEqual(matches[1]["product_image_id"], 9)

    def test_search_hydration_passes_through_detail_without_matches(self):
        matches, detail = hydrate_search_matches({"matches": [], "detail": "no similar products found"}, fetch_products_by_ids=lambda ids: [])

        self.assertEqual(matches, [])
        self.assertEqual(detail, "no similar products found")

    @patch("apps.core.views.proxy_search_image_with_threshold")
    @patch("apps.core.views.hydrate_search_matches")
    def test_search_proxy_wraps_search_results(self, mock_hydrate_search_matches, mock_proxy_search_image):
        mock_proxy_search_image.return_value = {
            "matches": [
                {"product_id": 11, "product_image_id": 7, "qdrant_id": "a", "score": 0.81},
                {"product_id": 22, "product_image_id": 8, "qdrant_id": "b", "score": 0.97},
            ]
        }
        mock_hydrate_search_matches.return_value = (
            [
                {
                    "id": 22,
                    "name": "High",
                    "price": "20.00",
                    "category": {"id": 1, "name": "Shoes", "slug": "shoes"},
                    "score": 0.97,
                },
                {
                    "id": 11,
                    "name": "Low",
                    "price": "10.00",
                    "category": {"id": 1, "name": "Shoes", "slug": "shoes"},
                    "score": 0.81,
                },
            ],
            None,
        )
        request = self.factory.post("/api/search/", {"image": make_image_file(), "score_threshold": "0.65"}, format="multipart")

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["matches"]], [22, 11])
        self.assertEqual(response.data["matches"][0]["score"], 0.97)
        self.assertEqual(response.data["matches"][1]["score"], 0.81)
        mock_proxy_search_image.assert_called_once()
        mock_hydrate_search_matches.assert_called_once()
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["image_name"], "query.png")
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["content_type"], "image/png")
        self.assertTrue(mock_proxy_search_image.call_args.kwargs["image_bytes"])
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["score_threshold"], 0.65)
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["limit"], 10)

    @patch("apps.core.views.proxy_search_image_with_threshold")
    def test_search_proxy_passes_through_ood_detail(self, mock_proxy_search_image):
        mock_proxy_search_image.return_value = {"detail": "no similar products found"}
        request = self.factory.post("/api/search/", {"image": make_image_file()}, format="multipart")

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "no similar products found")
        self.assertEqual(response.data["matches"], [])

    @patch("apps.core.views.hydrate_search_matches")
    @patch("apps.core.views.proxy_search_image_with_threshold")
    def test_search_proxy_translates_catalog_errors(self, mock_proxy_search_image, mock_hydrate_search_matches):
        mock_proxy_search_image.return_value = {"matches": [{"product_id": 11, "score": 0.81}]}
        mock_hydrate_search_matches.side_effect = CatalogServiceError("product service request failed")
        request = self.factory.post("/api/search/", {"image": make_image_file()}, format="multipart")

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "product service request failed")


class PageRenderTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def render_view(self, view, path="/"):
        response = view(self.factory.get(path))
        response.render()
        return response.content.decode("utf-8")

    def test_home_page_renders_storefront(self):
        content = self.render_view(LandingPageView.as_view())

        self.assertIn("Find the right car fast, then dive into a focused detail page.", content)
        self.assertIn("inventory-search", content)
        self.assertIn("__wamsInit", content)

    def test_car_detail_page_renders(self):
        response = CarDetailPageView.as_view()(self.factory.get("/cars/9/"), pk=9)
        response.render()
        content = response.content.decode("utf-8")

        self.assertIn("Dedicated detail page", content)
        self.assertIn("Five recommended alternatives from visual retrieval.", content)
        self.assertIn("data-car-id=\"9\"", content)

    def test_demo_page_renders_lab(self):
        content = self.render_view(DemoPageView.as_view(), path="/demo/")

        self.assertIn("Search flow, fully exposed.", content)
        self.assertIn("Top 10 hydrated product results ranked high to low.", content)
        self.assertIn("Click a result to find similar products.", content)
        self.assertNotIn("/api/gradcam/", content)
        self.assertNotIn("lab-overlay-preview", content)
        self.assertNotIn("gradcamWithImage", content)
        self.assertNotIn("renderOverlay", content)
        self.assertNotIn("setOverlayState", content)

    def test_auth_pages_render(self):
        views = [LoginPageView.as_view(), RegisterPageView.as_view(), ProfilePageView.as_view()]
        expected = ["/api/auth/login/", "/api/auth/register/", "/api/auth/profile/"]

        for view, marker in zip(views, expected):
            response = view(self.factory.get("/auth/"))
            response.render()
            content = response.content.decode("utf-8")
            self.assertIn(marker, content)

    def test_access_denied_page_renders(self):
        response = AccessDeniedPageView.as_view()(self.factory.get("/auth/access-denied/?next=/auth/seller/"))
        response.render()
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 403)
        self.assertIn("You do not have permission to open seller tools.", content)
        self.assertIn("/auth/login/", content)
        self.assertIn("/auth/seller/", content)

    def test_error_handlers_render_minimal_pages(self):
        for view, code, marker in [
            (bad_request_page, 400, "That request could not be processed."),
            (permission_denied_page, 403, "You do not have permission to open this area."),
            (page_not_found, 404, "Nothing is parked here."),
            (server_error_page, 500, "Something broke on our side."),
        ]:
            response = view(self.factory.get("/missing/"))
            response.render()
            content = response.content.decode("utf-8")

            self.assertEqual(response.status_code, code)
            self.assertIn(marker, content)
            self.assertIn("Apex Motors", content)


class _FakeUser:
    def __init__(self, *, role=None, token=None, is_authenticated=True):
        self.role = role
        self.token = token
        self.is_authenticated = is_authenticated


class GatewayPermissionTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = SellerWritePermission()

    def test_write_denied_for_client_role(self):
        request = self.factory.post("/api/products/", {"name": "x"}, format="json")
        request.user = _FakeUser(token={"role": "client"})

        allowed = self.permission.has_permission(request, None)

        self.assertFalse(allowed)

    def test_write_allowed_for_seller(self):
        seller_request = self.factory.post("/api/products/", {"name": "x"}, format="json")
        seller_request.user = _FakeUser(token={"role": "seller"})
        self.assertTrue(self.permission.has_permission(seller_request, None))
