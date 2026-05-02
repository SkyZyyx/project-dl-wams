from unittest.mock import MagicMock, patch
from urllib import error as urllib_error

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .views import health, ready


class SearchCoreHealthTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_health_is_ok(self):
        response = health(self.factory.get("/api/health/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["service"], "search_service")
        self.assertEqual(response.data["status"], "ok")

    @patch("apps.core.views.urllib_request.urlopen")
    @patch("apps.core.views.connection.cursor")
    def test_ready_is_ok_when_db_and_qdrant_are_up(self, mock_cursor, mock_urlopen):
        mock_cursor.return_value.__enter__.return_value = MagicMock()
        mock_response = MagicMock(status=200)
        mock_urlopen.return_value.__enter__.return_value = mock_response

        response = ready(self.factory.get("/api/ready/"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["db"])
        self.assertTrue(response.data["qdrant"])

    @patch("apps.core.views.urllib_request.urlopen", side_effect=urllib_error.URLError("down"))
    @patch("apps.core.views.connection.cursor")
    def test_ready_fails_when_qdrant_is_down(self, mock_cursor, _mock_urlopen):
        mock_cursor.return_value.__enter__.return_value = MagicMock()

        response = ready(self.factory.get("/api/ready/"))

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.data["qdrant"])
