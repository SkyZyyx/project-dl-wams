# End To End Runbook

This repo now runs as a split stack:

- `main_service` is the gateway/UI
- `user_service` owns auth and users
- `product_service` owns catalog data
- `order_service` owns orders
- `search_service` owns image search and Grad-CAM

## 1. Prerequisites

- Docker
- Docker Compose

## 2. Start Everything

From the repo root:

```bash
docker compose up -d --build
```

Wait for the services to come up. The important ones are:

- `main_service` on `http://localhost:8000`
- `user_service` on `http://localhost:8001`
- `product_service` on `http://localhost:8002`
- `order_service` on `http://localhost:8003`
- `search_service` on `http://localhost:8004`
- public Nginx entrypoint on `http://localhost:8080`

## 3. Seed Demo Data

Seed the catalog from the product service:

```bash
docker compose exec product_service python manage.py seed_demo
```

This step can take a while the first time because it downloads the demo dataset.
The seeder now pulls `jutrera/stanford-car-dataset-by-classes-folder` through KaggleHub.

### Kaggle Credentials (Required For Seeding)

KaggleHub downloads from Kaggle, so the `product_service` container needs Kaggle credentials.

Option A (recommended): export env vars on your machine, then start Docker:

```bash
export KAGGLE_USERNAME="your_kaggle_username"
export KAGGLE_API_TOKEN="your_kaggle_api_token"
docker compose up -d --build
docker compose exec product_service python manage.py seed_demo
```

Option B: mount a `kaggle.json` into the container:

1. Create `~/.kaggle/kaggle.json` on your machine (from Kaggle Account -> API -> Create New Token).
2. Add a volume mapping in `docker-compose.yml` for `product_service`:

```yaml
volumes:
  - ~/.kaggle/kaggle.json:/root/.kaggle/kaggle.json:ro
```

Then run:

```bash
docker compose up -d --build
docker compose exec product_service python manage.py seed_demo
```

The seed command now builds one product from each 5-image chunk of the dataset, so each seeded product carries multiple angles instead of a single photo.

## 4. Verify The Stack

Open these URLs:

- Main app: `http://localhost:8080/`
- Demo page: `http://localhost:8080/demo/`
- Main health check: `http://localhost:8080/api/health/`
- User health check: `http://localhost:8001/api/health/`
- Product health check: `http://localhost:8002/api/health/`
- Order health check: `http://localhost:8003/api/health/`
- Search health check: `http://localhost:8004/api/health/`

## 5. Smoke Test

Run the gateway smoke command:

```bash
docker compose exec main_service python manage.py demo_smoke
```

Run the search-service tests:

```bash
docker compose exec search_service python manage.py test apps.search.tests
```

Run the gateway tests:

```bash
docker compose exec main_service python manage.py test apps.core.tests
```

## 6. Optional Colab Model Import

If you trained a model in Colab, mount it into `./models` and set one of these env vars before starting Docker:

- `DINOv2_FINETUNED_SOURCE` for a Hugging Face-style folder created with `save_pretrained(...)`
- `DINOv2_FINETUNED_CHECKPOINT_PATH` for a `.pt` or `.pth` file
- `DINOv2_TRANSFER_CHECKPOINT_PATH` for the transfer-learning checkpoint
- `CLIP_VIT_B32_CHECKPOINT_PATH` for a CLIP checkpoint

Example:

```bash
export DINOv2_FINETUNED_CHECKPOINT_PATH=/models/my_colab_model.pt
docker compose up -d --build
```

## 7. What Was Removed

The old monolith-only catalog and order apps inside `main_service` were removed. The gateway now talks to the dedicated services over HTTP, which is what you want for a true microservice split.
