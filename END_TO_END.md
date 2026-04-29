# End To End Runbook

Use this from a fresh clone. It starts the full Docker stack, seeds demo cars,
builds the image-search index, then gives commands to verify the app works.

## 1. Prerequisites

- Docker
- Docker Compose
- Kaggle account and API token for the demo dataset

Create a Kaggle token from `Kaggle -> Account -> API -> Create New Token`.
You need `KAGGLE_USERNAME` and `KAGGLE_API_TOKEN`.

## 2. Configure Environment

From the repo root:

```bash
cp .env.example .env
```

Edit `.env` and add your Kaggle values:

```bash
KAGGLE_USERNAME=your_kaggle_username
KAGGLE_API_TOKEN=your_kaggle_api_token
```

For a first run, keep this model setting unless you also have the trained
checkpoint mounted in `./models`:

```bash
DEFAULT_SEARCH_MODEL=dinov2_base_pretrained
```

Do not use `DEFAULT_SEARCH_MODEL=dinov2_base_triplet_finetuned` unless
`DINOV2_TRIPLET_FINETUNED_CHECKPOINT_PATH` points to a real file in the
container, for example `/models/retrieval_model.pth`.

## 3. Start The Stack

```bash
docker compose up -d --build
```

Wait until containers are up:

```bash
docker compose ps
```

Expected app ports:

- Main gateway/UI: `http://localhost:8080`
- Main service direct: `http://localhost:8000`
- User service: `http://localhost:8001`
- Product service: `http://localhost:8002`
- Order service: `http://localhost:8003`
- Search service: `http://localhost:8004`
- Qdrant: `http://localhost:6333/dashboard`

## 4. Seed Demo Products

```bash
docker compose exec product_service python manage.py seed_demo
```

Create local demo admins:

```bash
docker compose exec product_service python manage.py seed_demo_admin
docker compose exec search_service python manage.py seed_demo_admin
docker compose exec user_service python manage.py seed_demo_admin
```

Open the admin operation dashboards:

- `http://localhost:8002/admin/ops/`
- `http://localhost:8004/admin/ops/`

First run can take a while because it downloads
`jutrera/stanford-car-dataset-by-classes-folder` through KaggleHub.

## 5. Build Image Search Index

If Qdrant already has old data, reset the active collection first. This avoids
the bug where search returns old product IDs and the gateway hydrates nothing.

```bash
docker compose exec search_service python manage.py shell -c "from apps.search.services.model_registry import get_default_model_id, get_model_spec; from apps.search.services.qdrant import get_client, ensure_collection, clear_collection_mean_vector_cache; spec=get_model_spec(get_default_model_id()); client=get_client(); exists=client.collection_exists(spec.collection_name) if hasattr(client, 'collection_exists') else spec.collection_name in {c.name for c in client.get_collections().collections}; client.delete_collection(spec.collection_name) if exists else None; ensure_collection(); clear_collection_mean_vector_cache(); print('reset', spec.collection_name)"
```

Then rebuild the index from the current product DB:

```bash
docker compose exec product_service python manage.py shell -c "from apps.products.models import ProductImage; ProductImage.objects.update(indexed=False, qdrant_id=None); print('marked', ProductImage.objects.count())"
docker compose exec product_service python manage.py reindex_product_images
```

The reindex step is slow because every product image is embedded and sent to
Qdrant. Let it finish.

## 6. Health Checks

```bash
curl -s http://localhost:8080/api/health/
curl -s http://localhost:8001/api/health/
curl -s http://localhost:8002/api/health/
curl -s http://localhost:8003/api/health/
curl -s http://localhost:8004/api/health/
```

Each should return JSON with `"status":"ok"`.

## 7. Test Image Search

Open UI:

```text
http://localhost:8080/
```

Upload a car image in the visual search form.

If this repo includes `bmw.jpeg` and `audi.jpg` in the project root, test the
API directly:

```bash
curl -s -F image=@bmw.jpeg http://localhost:8080/api/search/
curl -s -F image=@audi.jpg http://localhost:8080/api/search/
```

Expected: response contains `"matches"` with product objects, not an empty list.

You can compare the raw search service against the gateway:

```bash
curl -s -F image=@bmw.jpeg http://localhost:8004/api/search/
curl -s -F image=@bmw.jpeg http://localhost:8000/api/search/
```

Search service returns raw IDs/scores. Gateway returns hydrated products.

## 8. Test Recommendations

Open any car detail page from the UI, or use one product ID returned by search:

```text
http://localhost:8080/cars/<product_id>/
```

Recommendations should load below the car details. If they do not, check that
the image index was rebuilt after seeding.

## 9. Automated Smoke Tests

```bash
docker compose exec main_service python manage.py demo_smoke
docker compose exec search_service python manage.py test apps.search.tests
docker compose exec main_service python manage.py test apps.core.tests
```

## 10. Useful Logs

```bash
docker compose logs --tail=100 main_service
docker compose logs --tail=100 product_service
docker compose logs --tail=100 search_service
docker compose logs --tail=100 qdrant
```

If image search returns no UI results but raw search returns IDs, the usual
cause is stale Qdrant vectors. Run section 5 again.

For a one-shot local bootstrap, run:

```bash
bash bootstrap-demo.sh
```

## 11. Stop Or Reset

Stop containers, keep data:

```bash
docker compose down
```

Full reset, delete DBs and Qdrant data:

```bash
docker compose down -v
```

After a full reset, run sections 3 through 7 again.
