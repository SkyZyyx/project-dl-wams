from __future__ import annotations

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .operations import delete_all_products, delete_product, get_catalog_stats, reindex_all_product_images
from .models import Product


def product_operations_view(request):
    stats = get_catalog_stats()
    recent_products = Product.objects.select_related("category").order_by("-created_at", "-id")[:24]

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "delete_product":
            product_id = request.POST.get("product_id")
            if not product_id or not product_id.isdigit():
                messages.error(request, "Pick a valid product to delete.")
            else:
                deleted = delete_product(int(product_id))
                if deleted:
                    messages.success(request, f"Deleted product #{product_id}.")
                else:
                    messages.warning(request, f"Product #{product_id} was not found.")

        elif action == "delete_all_products":
            confirmation = request.POST.get("confirmation", "").strip().upper()
            if confirmation != "DELETE ALL":
                messages.error(request, 'Type DELETE ALL before removing the entire catalog.')
            else:
                deleted = delete_all_products()
                messages.success(request, f"Deleted {deleted} catalog row(s).")

        elif action == "reindex_all_images":
            indexed, skipped = reindex_all_product_images()
            if skipped:
                messages.warning(request, f"Reindexed {indexed} image(s); skipped {skipped}.")
            else:
                messages.success(request, f"Reindexed {indexed} image(s).")

        return redirect("product-admin-ops")

    return TemplateResponse(
        request,
        "admin/products/operations.html",
        {
            **admin.site.each_context(request),
            "title": "Catalog operations",
            "stats": stats,
            "recent_products": recent_products,
            "ops_url": reverse("product-admin-ops"),
        },
    )
