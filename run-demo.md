# Run Demo

## Prerequisites
- Docker
- Docker Compose

## Setup
1. Clone the repo.
2. Copy the example env file:
   ```bash
   cp .env.example .env
   ```
3. Start the stack:
   ```bash
   docker compose up -d --build
   ```
4. Seed demo data:
   ```bash
   docker compose exec product_service python manage.py seed_demo
   ```

## Notes
- The seed command now uses KaggleHub to download `jutrera/stanford-car-dataset-by-classes-folder`.
- If you want a different Kaggle dataset later, pass `--dataset-id <owner/dataset-name>`.
- Each seeded product now gets a chunk of 5 images from the dataset, so product cards can show multiple angles.
- The `product_service` container reads `KAGGLE_USERNAME` and `KAGGLE_API_TOKEN`.
- The search service and Qdrant must be running for seeding and search features to work. `docker compose up -d --build` starts both.
- To import a Colab-trained model, mount it into `./models` and point one of these env vars at it:
  - `DINOV2_FINETUNED_SOURCE` for a `save_pretrained(...)` folder
  - `DINOV2_FINETUNED_CHECKPOINT_PATH` for a `.pt` / `.pth` checkpoint
  - `DINOV2_TRIPLET_FINETUNED_CHECKPOINT_PATH` for notebook exports like `retrieval_model.pth` from triplet fine-tuning
  - `DINOV2_TRIPLET_FINETUNED_SOURCE` defaults to `vit_base_patch14_dinov2.lvd142m` (matches your notebook backbone)
  - `DINOV2_TRIPLET_FINETUNED_VECTOR_SIZE` defaults to `512` (matches your notebook projection head)
  - `DEFAULT_SEARCH_MODEL=dinov2_base_triplet_finetuned` to make indexing/search use the triplet export
  - `CLIP_VIT_B32_CHECKPOINT_PATH` or `DINOV2_TRANSFER_CHECKPOINT_PATH` for other variants

## Open the app
- Main app: `http://localhost:8080/`
- Main API health check: `http://localhost:8080/api/health/`
- User service health check: `http://localhost:8001/api/health/`
- Product service health check: `http://localhost:8002/api/health/`
- Order service health check: `http://localhost:8003/api/health/`
- Search service health check: `http://localhost:8004/api/health/`

## Useful endpoints
- Demo page: `http://localhost:8080/demo/`
- Search API: `http://localhost:8080/api/search/`
- Grad-CAM API: `http://localhost:8080/api/gradcam/`
