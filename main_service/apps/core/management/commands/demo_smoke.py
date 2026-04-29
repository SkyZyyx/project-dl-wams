import json
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand, CommandError, call_command
from django.test import Client


def make_image_file(name: str = "smoke.png", size: tuple[int, int] = (128, 128), color=(120, 60, 30)):
    from PIL import Image

    buffer = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class Command(BaseCommand):
    help = "Run the gateway smoke check."

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        client = Client()

        home_response = client.get("/")
        if home_response.status_code != 200:
            raise CommandError(f"home page failed: {home_response.status_code}")

        response = client.get("/demo/")
        if response.status_code != 200:
            raise CommandError(f"demo page failed: {response.status_code}")

        with patch("apps.core.views.proxy_search_image_with_threshold") as mock_search_proxy, patch(
            "apps.core.views.hydrate_search_matches"
        ) as mock_hydrate_search_matches:
            mock_search_proxy.return_value = {
                "matches": [
                    {
                        "product_id": 101,
                        "product_image_id": 7,
                        "qdrant_id": "abc",
                        "score": 0.93,
                    }
                ]
            }
            mock_hydrate_search_matches.return_value = [
                {
                    "id": 101,
                    "name": "Smoke Product",
                    "price": "9.99",
                    "category": {"id": 1, "name": "Smoke", "slug": "smoke"},
                    "score": 0.93,
                }
            ], None
            search_response = client.post(
                "/api/search/",
                {"image": make_image_file(name="query.png"), "score_threshold": "0.40"},
            )

        if search_response.status_code != 200:
            raise CommandError(f"search endpoint failed: {search_response.status_code}")

        matches = json.loads(search_response.content.decode("utf-8")).get("matches")
        if not matches:
            raise CommandError("search endpoint returned no matches")

        self.stdout.write(self.style.SUCCESS("gateway smoke check passed"))
