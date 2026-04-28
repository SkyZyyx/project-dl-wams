from io import BytesIO
from unittest.mock import patch

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory

from apps.core.views import DemoPageView
from apps.users.views import LandingPageView, LoginPageView, ProfilePageView, RegisterPageView
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

    @patch("apps.core.views.fetch_products_by_ids")
    @patch("apps.core.views.proxy_search_image_with_threshold")
    def test_search_proxy_hydrates_and_sorts_matches(self, mock_proxy_search_image, mock_fetch_products_by_ids):
        mock_proxy_search_image.return_value = {
            "matches": [
                {"product_id": 11, "product_image_id": 7, "qdrant_id": "a", "score": 0.81},
                {"product_id": 22, "product_image_id": 8, "qdrant_id": "b", "score": 0.97},
            ]
        }
        mock_fetch_products_by_ids.return_value = [
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
        request = self.factory.post("/api/search/", {"image": make_image_file(), "score_threshold": "0.65"}, format="multipart")

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["matches"]], [22, 11])
        self.assertEqual(response.data["matches"][0]["score"], 0.97)
        self.assertEqual(response.data["matches"][1]["score"], 0.81)
        mock_proxy_search_image.assert_called_once()
        mock_fetch_products_by_ids.assert_called_once_with([11, 22])
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["image_name"], "query.png")
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["content_type"], "image/png")
        self.assertTrue(mock_proxy_search_image.call_args.kwargs["image_bytes"])
        self.assertEqual(mock_proxy_search_image.call_args.kwargs["score_threshold"], 0.65)

    @patch("apps.core.views.proxy_search_image_with_threshold")
    def test_search_proxy_passes_through_ood_detail(self, mock_proxy_search_image):
        mock_proxy_search_image.return_value = {"detail": "no similar products found"}
        request = self.factory.post("/api/search/", {"image": make_image_file()}, format="multipart")

        response = SearchView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["detail"], "no similar products found")
        self.assertEqual(response.data["matches"], [])


class PageRenderTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def render_view(self, view, path="/"):
        response = view(self.factory.get(path))
        response.render()
        return response.content.decode("utf-8")

    def test_home_page_renders_storefront(self):
        content = self.render_view(LandingPageView.as_view())

        self.assertIn("Cars for sale, auction energy.", content)
        self.assertIn("auction-card", content)
        self.assertIn("__wamsInit", content)

    def test_demo_page_renders_lab(self):
        content = self.render_view(DemoPageView.as_view(), path="/demo/")

        self.assertIn("Search flow, fully exposed.", content)
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
