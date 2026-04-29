from django.contrib import admin

from .models import Category, Product, ProductImage
from .lifecycle import index_product_image_record

admin.site.site_header = "Apex Motors Catalog Control"
admin.site.site_title = "Catalog Control"
admin.site.index_title = "Catalog operations"


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

            index_product_image_record(image)
            updated += 1

        self.message_user(request, f"Re-indexed {updated} image(s).")

    actions = (reindex_selected_images,)
