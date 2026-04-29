from __future__ import annotations

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .operations import clear_active_cache, get_search_operations_state, reset_active_collection


def search_operations_view(request):
    state = get_search_operations_state()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "reset_collection":
            collection_name = reset_active_collection()
            messages.success(request, f"Reset {collection_name}.")
        elif action == "clear_cache":
            collection_name = clear_active_cache()
            messages.success(request, f"Cleared cache for {collection_name}.")

        return redirect("search-admin-ops")

    return TemplateResponse(
        request,
        "admin/search/operations.html",
        {
            **admin.site.each_context(request),
            "title": "Search operations",
            "state": state,
            "ops_url": reverse("search-admin-ops"),
        },
    )
