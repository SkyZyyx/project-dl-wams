from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_SERVICE_ROOT = REPO_ROOT / "search_service"


def bootstrap_search_service_django() -> None:
    search_service_root = str(SEARCH_SERVICE_ROOT)
    if search_service_root not in sys.path:
        sys.path.insert(0, search_service_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    django.setup()
