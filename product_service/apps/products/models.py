from base64 import b64encode
from io import BytesIO

from django.db import models
from django.utils.text import slugify
from PIL import Image, ImageOps


def generate_thumbnail_b64(image_file, width=256):
    try:
        with Image.open(image_file) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")

            if image.width > width:
                height = int(image.height * (width / image.width))
                image = image.resize((width, height), Image.Resampling.LANCZOS)

            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=85, optimize=True)
            return b64encode(buffer.getvalue()).decode("utf-8")
    finally:
        if hasattr(image_file, "seek"):
            image_file.seek(0)


class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, related_name="products", null=True, blank=True)
    seller_username = models.CharField(max_length=150, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/")
    thumbnail_b64 = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False)
    indexed = models.BooleanField(default=False)
    qdrant_id = models.CharField(max_length=255, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "uploaded_at", "id"]

    def save(self, *args, **kwargs):
        if self.image:
            self.thumbnail_b64 = generate_thumbnail_b64(self.image)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_id}:{self.id}"
