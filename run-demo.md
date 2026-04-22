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
   docker compose exec main_service python manage.py seed_demo
   ```

## Notes
- The first seed run downloads the UT Zappos50K dataset, so it can take a while.
- The search service and Qdrant must be running for seeding and search features to work. `docker compose up -d --build` starts both.

## Open the app
- Main app: `http://localhost:8080/`
- Main API health check: `http://localhost:8080/api/health/`
- Search service health check: `http://localhost:8001/api/health/`

## Useful endpoints
- Demo page: `http://localhost:8080/demo/`
- Search API: `http://localhost:8080/api/search/`
- Grad-CAM API: `http://localhost:8080/api/gradcam/`
