from django.contrib import admin

from .models import Category, Product, ProductImage
from .services.search_proxy import index_product_image


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")
    search_fields = ("name", "slug")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ("thumbnail_b64", "uploaded_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "price", "created_at")
    list_select_related = ("category",)
    search_fields = ("name", "description")
    list_filter = ("category",)
    inlines = (ProductImageInline,)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "is_primary", "indexed", "uploaded_at")
    list_select_related = ("product",)
    search_fields = ("product__name",)
    list_filter = ("is_primary", "indexed")

    @admin.action(description="Re-index selected images")
    def reindex_selected_images(self, request, queryset):
        updated = 0
        for image in queryset.select_related("product"):
            if not image.image:
                continue

            with image.image.open("rb") as image_file:
                response = index_product_image(
                    product_id=image.product_id,
                    product_image_id=image.id,
                    image_name=image.image.name.rsplit("/", 1)[-1],
                    image_bytes=image_file.read(),
                    content_type=getattr(image.image.file, "content_type", "application/octet-stream"),
                )

            ProductImage.objects.filter(pk=image.pk).update(indexed=True, qdrant_id=response.get("qdrant_id"))
            updated += 1

        self.message_user(request, f"Re-indexed {updated} image(s).")

    actions = (reindex_selected_images,)
