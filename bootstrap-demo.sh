#!/usr/bin/env bash
set -euo pipefail

wait_for_url() {
  local url="$1"
  local label="$2"

  until curl -fsS "$url" >/dev/null; do
    printf 'Waiting for %s...\n' "$label"
    sleep 2
  done
}

printf 'Starting stack...\n'
docker compose up -d --build

wait_for_url "http://localhost:8002/api/health/" "product_service"
wait_for_url "http://localhost:8004/api/health/" "search_service"

printf 'Seeding demo products...\n'
docker compose exec -T product_service python manage.py seed_demo

printf 'Reindexing product images...\n'
docker compose exec -T product_service python manage.py reindex_product_images

printf 'Seeding product admin...\n'
docker compose exec -T product_service python manage.py seed_demo_admin

printf 'Seeding search admin...\n'
docker compose exec -T search_service python manage.py seed_demo_admin

printf 'Seeding main-app admin...\n'
docker compose exec -T user_service python manage.py seed_demo_admin

printf 'Demo bootstrap complete.\n'
