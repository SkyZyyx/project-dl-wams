from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .views import health, ready


class ProductCoreHealthTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_health_is_ok(self):
        response = health(self.factory.get("/api/health/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["service"], "product_service")
        self.assertEqual(response.data["status"], "ok")

    @patch("apps.core.views.connection.cursor")
    def test_ready_is_ok_when_db_is_up(self, mock_cursor):
        mock_cursor.return_value.__enter__.return_value = MagicMock()

        response = ready(self.factory.get("/api/ready/"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["db"])

    @patch("apps.core.views.connection.cursor", side_effect=Exception("db down"))
    def test_ready_fails_when_db_is_down(self, _mock_cursor):
        response = ready(self.factory.get("/api/ready/"))

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.data["db"])
