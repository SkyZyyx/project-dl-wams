import json
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.test import Client

from apps.products.models import Category, Product, ProductImage


def make_image_file(name: str = "smoke.png", size: tuple[int, int] = (128, 128), color=(120, 60, 30)):
    from PIL import Image

    buffer = BytesIO()
    image = Image.new("RGB", size, color=color)
    image.save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class Command(BaseCommand):
    help = "Run the milestone 8 demo smoke check."

    def handle(self, *args, **options):
        call_command("migrate", interactive=False, verbosity=0)

        client = Client()
        image = make_image_file()

        category, _ = Category.objects.get_or_create(name="Smoke")
        product, _ = Product.objects.get_or_create(
            name="Smoke Product",
            category=category,
            defaults={"description": "", "price": "9.99"},
        )

        with patch("apps.products.signals.index_product_image") as mock_index_product_image:
            mock_index_product_image.return_value = {"qdrant_id": "smoke-qdrant"}
            product_image = ProductImage.objects.create(product=product, image=image, is_primary=True)

        product_image.refresh_from_db()
        if not product_image.indexed:
            raise CommandError("product image was not indexed during smoke setup")

        home_response = client.get("/")
        if home_response.status_code != 200:
            raise CommandError(f"home page failed: {home_response.status_code}")

        response = client.get("/demo/")
        if response.status_code != 200:
            raise CommandError(f"demo page failed: {response.status_code}")

        with patch("apps.core.views.proxy_search_image_with_threshold") as mock_search_proxy:
            mock_search_proxy.return_value = {
                "matches": [
                    {
                        "product_id": product.id,
                        "product_image_id": product_image.id,
                        "qdrant_id": "abc",
                        "score": 0.93,
                    }
                ]
            }
            search_response = client.post(
                "/api/search/",
                {"image": make_image_file(name="query.png"), "score_threshold": "0.40"},
            )

        if search_response.status_code != 200:
            raise CommandError(f"search endpoint failed: {search_response.status_code}")

        if not json.loads(search_response.content.decode("utf-8")).get("matches"):
            raise CommandError("search endpoint returned no matches")

        with patch("apps.core.views.proxy_gradcam_image") as mock_gradcam_proxy:
            mock_gradcam_proxy.return_value = {"overlay_b64": "abc", "width": 128, "height": 128}
            gradcam_response = client.post("/api/gradcam/", {"image": make_image_file(name="overlay.png")})

        if gradcam_response.status_code != 200:
            raise CommandError(f"gradcam endpoint failed: {gradcam_response.status_code}")

        self.stdout.write(self.style.SUCCESS("demo smoke check passed"))
