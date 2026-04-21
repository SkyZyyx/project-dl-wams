# PRD — Visual Search System for E-Commerce
**Project type:** University project  
**Stack:** Django DRF × 2 services · DINOv2/CLIP · Qdrant · PostgreSQL · Docker Compose  
**Storage:** Local filesystem (no S3)  
**Last updated:** 2026-04-20

---

## 1. Overview

A dual-service Django REST Framework system that lets users upload a query image and receive visually similar products from the catalog. The main service handles products, users, and orders; the search service handles all AI/ML logic in isolation.

---

## 2. Goals

| Goal | Description |
|------|-------------|
| Visual search | User uploads any image → get ranked similar products |
| Clean separation | AI code never touches business logic |
| Cost-zero infra | Local storage, free-tier Qdrant (or self-hosted), no S3 |
| University demo | Grad-CAM heatmap overlay, admin indexing UI |

---

## 3. Non-Goals

- Mobile app
- Payment integration (out of scope for this version)
- Production-grade auth (basic JWT is enough)

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────┐
│              Django + DRF  (main_service)            │
│         Products | Orders | Users | Admin            │
│              http://localhost:8000                   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (requests library)
                       │
┌──────────────────────▼──────────────────────────────┐
│           Django + DRF  (search_service)             │
│     Embedding | Detection | Quality | OOD | Qdrant  │
│              http://localhost:8001                   │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
         ┌────▼────┐      ┌─────▼────┐
         │ Qdrant  │      │PostgreSQL│
         │  :6333  │      │  :5432   │
         └─────────┘      └──────────┘
```

---

## 5. Project Structure

```
ecommerce/
├── main_service/
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   └── urls.py
│   ├── apps/
│   │   ├── products/
│   │   │   ├── models.py          ← Product, ProductImage
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   ├── users/
│   │   ├── orders/
│   │   └── search/                ← Thin proxy; forwards to search_service
│   │       ├── views.py
│   │       └── urls.py
│   ├── media/                     ← LOCAL image storage (MEDIA_ROOT)
│   └── requirements.txt
│
├── search_service/
│   ├── manage.py
│   ├── config/
│   │   ├── settings.py
│   │   └── urls.py
│   ├── apps/
│   │   └── core/
│   │       ├── views.py
│   │       ├── serializers.py
│   │       ├── urls.py
│   │       └── services/
│   │           ├── embedder.py    ← DINOv2 / CLIP
│   │           ├── detector.py    ← YOLOv8 / Grounding DINO
│   │           ├── background.py  ← rembg
│   │           ├── quality.py     ← blur, brightness checks
│   │           ├── ood.py         ← out-of-distribution filter
│   │           └── qdrant.py      ← Qdrant client wrapper
│   └── requirements.txt
│
├── docker-compose.yml
└── nginx/
    └── nginx.conf
```

---

## 6. Data Models

### main_service

```python
# apps/products/models.py

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

class Product(models.Model):
    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    category    = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

class ProductImage(models.Model):
    product       = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image         = models.ImageField(upload_to='products/%Y/%m/')   # saved to MEDIA_ROOT
    thumbnail_b64 = models.TextField(blank=True)                     # 256px base64, no S3 needed
    is_primary    = models.BooleanField(default=False)
    indexed       = models.BooleanField(default=False)               # True after Qdrant indexing
    qdrant_id     = models.UUIDField(null=True, blank=True)
    uploaded_at   = models.DateTimeField(auto_now_add=True)
```

---

## 7. Image Storage Strategy (Local, No S3)

### 7a. Saving uploaded images

```python
# settings.py  (main_service)
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

```python
# urls.py  (main_service/config)  — dev only
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### 7b. Generating thumbnails with BytesIO + base64

```python
# apps/products/utils.py
import base64
from io import BytesIO
from PIL import Image

TARGET_WIDTH = 256

def make_thumbnail_b64(image_field) -> str:
    """
    Read an ImageField, resize to TARGET_WIDTH (preserving aspect ratio),
    encode as JPEG base64 string.  No S3, no external service.
    """
    img = Image.open(image_field).convert("RGB")

    # Preserve aspect ratio
    ratio  = TARGET_WIDTH / img.width
    height = int(img.height * ratio)
    img    = img.resize((TARGET_WIDTH, height), Image.LANCZOS)

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode("utf-8")
```

```python
# apps/products/views.py  (on ProductImage save)
class ProductImageUploadView(generics.CreateAPIView):
    def perform_create(self, serializer):
        instance = serializer.save(product=self.get_product())
        # Generate thumbnail inline, no celery needed for uni project
        instance.thumbnail_b64 = make_thumbnail_b64(instance.image)
        instance.save(update_fields=['thumbnail_b64'])
        # Trigger indexing in search_service (async via thread or celery)
        index_product_image.delay(instance.id)   # or call synchronously
```

### 7c. Sending image bytes to search_service

```python
# apps/search/views.py  (proxy)
import requests

class SearchView(APIView):
    def post(self, request):
        uploaded = request.FILES.get('image')
        
        # Read bytes once; forward as multipart to search_service
        image_bytes = uploaded.read()
        
        resp = requests.post(
            'http://search_service:8001/api/search/',
            files={'image': (uploaded.name, image_bytes, uploaded.content_type)},
            timeout=10,
        )
        
        matches = resp.json().get('matches', [])
        product_ids = [m['product_id'] for m in matches]
        scores      = {m['product_id']: m['score'] for m in matches}
        
        products = Product.objects.filter(id__in=product_ids).prefetch_related('images')
        serializer = ProductSerializer(products, many=True)
        
        # Attach similarity scores to response
        data = serializer.data
        for item in data:
            item['score'] = scores.get(item['id'], 0)
        data.sort(key=lambda x: x['score'], reverse=True)
        
        return Response(data)
```

---

## 8. Search Service — Embedding Pipeline

### 8a. Embedder (DINOv2 zero-shot MVP)

```python
# search_service/apps/core/services/embedder.py
import torch
from PIL import Image
from io import BytesIO
from transformers import AutoImageProcessor, AutoModel

MODEL_NAME = "facebook/dinov2-base"   # swap to dinov2-large for better accuracy

class DINOv2Embedder:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
            cls._instance.model     = AutoModel.from_pretrained(MODEL_NAME)
            cls._instance.model.eval()
        return cls._instance

    def embed(self, image_bytes: bytes) -> list[float]:
        img    = Image.open(BytesIO(image_bytes)).convert("RGB")
        inputs = self.processor(images=img, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
        # CLS token → 768-dim vector (dinov2-base)
        vector = outputs.last_hidden_state[:, 0, :].squeeze().tolist()
        return vector
```

### 8b. Quality checker

```python
# search_service/apps/core/services/quality.py
import cv2
import numpy as np
from io import BytesIO
from PIL import Image

def check_quality(image_bytes: bytes) -> dict:
    img_pil = Image.open(BytesIO(image_bytes)).convert("RGB")
    img_cv  = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    gray    = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    blur_score  = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness  = gray.mean()
    
    return {
        "blur_score":  blur_score,
        "brightness":  brightness,
        "is_blurry":   blur_score < 50,
        "too_dark":    brightness < 30,
        "too_bright":  brightness > 240,
        "ok":          blur_score >= 50 and 30 <= brightness <= 240,
    }
```

### 8c. Qdrant wrapper

```python
# search_service/apps/core/services/qdrant.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
)
import uuid
from django.conf import settings

COLLECTION = "product_images"
VECTOR_DIM  = 768   # dinov2-base; change to 512 for CLIP ViT-B/32

client = QdrantClient(url=settings.QDRANT_URL)   # e.g. http://qdrant:6333

def ensure_collection():
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )

def index_vector(product_id: int, image_id: int, vector: list[float]) -> str:
    point_id = str(uuid.uuid4())
    client.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(
            id=point_id,
            vector=vector,
            payload={"product_id": product_id, "image_id": image_id},
        )],
    )
    return point_id

def search_similar(vector: list[float], top_k: int = 20) -> list[dict]:
    hits = client.search(
        collection_name=COLLECTION,
        query_vector=vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {"product_id": h.payload["product_id"], "score": h.score}
        for h in hits
    ]

def delete_by_product(product_id: int):
    client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="product_id", match=MatchValue(value=product_id))]
        ),
    )
```

---

## 9. API Endpoints

### main_service (port 8000)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/products/` | Create product |
| `GET` | `/api/products/` | List products |
| `GET` | `/api/products/<id>/` | Product detail |
| `POST` | `/api/products/<id>/images/` | Upload image (triggers indexing) |
| `DELETE` | `/api/products/<id>/images/<img_id>/` | Delete image |
| `POST` | `/api/search/` | Visual search (proxied) |
| `GET` | `/api/categories/` | List categories |

### search_service (port 8001)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/index/` | Index a product image |
| `POST` | `/api/search/` | Search by image bytes |
| `DELETE` | `/api/index/<product_id>/` | Remove product vectors |
| `GET` | `/api/health/` | Liveness check |

---

## 10. Search Service Views

```python
# search_service/apps/core/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.embedder  import DINOv2Embedder
from .services.quality   import check_quality
from .services.qdrant    import ensure_collection, index_vector, search_similar, delete_by_product

embedder = DINOv2Embedder()

class IndexView(APIView):
    def post(self, request):
        image_bytes = request.FILES['image'].read()
        product_id  = int(request.data['product_id'])
        image_id    = int(request.data['image_id'])

        quality = check_quality(image_bytes)
        if not quality['ok']:
            return Response({'error': 'Image quality too low', 'detail': quality},
                            status=status.HTTP_400_BAD_REQUEST)

        ensure_collection()
        vector   = embedder.embed(image_bytes)
        point_id = index_vector(product_id, image_id, vector)

        return Response({'point_id': point_id, 'status': 'indexed'})


class SearchView(APIView):
    def post(self, request):
        image_bytes = request.FILES['image'].read()

        quality = check_quality(image_bytes)
        if not quality['ok']:
            return Response({'error': 'Image quality too low', 'detail': quality},
                            status=status.HTTP_400_BAD_REQUEST)

        vector  = embedder.embed(image_bytes)
        matches = search_similar(vector, top_k=20)

        return Response({'matches': matches})


class DeleteIndexView(APIView):
    def delete(self, request, product_id):
        delete_by_product(product_id)
        return Response({'status': 'deleted'})


class HealthView(APIView):
    def get(self, request):
        return Response({'status': 'ok'})
```

---

## 11. docker-compose.yml

```yaml
version: '3.9'

services:

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB:       ecommerce
      POSTGRES_USER:     postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  main_service:
    build: ./main_service
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./main_service:/app
      - media_files:/app/media          # shared local storage
    ports:
      - "8000:8000"
    env_file: ./main_service/.env
    depends_on:
      - postgres
      - search_service

  search_service:
    build: ./search_service
    command: python manage.py runserver 0.0.0.0:8001
    volumes:
      - ./search_service:/app
      - media_files:/app/media          # same volume — can read product images
    ports:
      - "8001:8001"
    env_file: ./search_service/.env
    depends_on:
      - qdrant

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf
      - media_files:/media              # serve /media/ directly
    depends_on:
      - main_service

volumes:
  postgres_data:
  qdrant_data:
  media_files:                          # replaces S3 — shared named volume
```

---

## 12. Environment Variables

### main_service/.env
```
SECRET_KEY=changeme
DEBUG=True
DB_NAME=ecommerce
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=postgres
DB_PORT=5432
SEARCH_SERVICE_URL=http://search_service:8001
MEDIA_ROOT=/app/media
```

### search_service/.env
```
SECRET_KEY=changeme
DEBUG=True
QDRANT_URL=http://qdrant:6333
MEDIA_ROOT=/app/media
```

---

## 13. Implementation Phases

### Phase 0 — Infra skeleton *(~1 day)*
- [ ] `docker-compose.yml` with postgres, qdrant, nginx
- [ ] Both Django projects created, DRF installed
- [ ] `health` endpoint on search_service returns `200 ok`
- [ ] nginx routes `/api/` → main_service, `/media/` → volume

### Phase 1 — Product CRUD + local image upload *(~1 day)*
- [ ] `Product`, `ProductImage` models + migrations
- [ ] `ImageField` with `MEDIA_ROOT` saving
- [ ] `make_thumbnail_b64()` runs on upload, stored in DB
- [ ] `GET /api/products/<id>/` returns `thumbnail_b64` in response

### Phase 2 — Embedding pipeline *(~1 day)*
- [ ] DINOv2Embedder singleton in search_service
- [ ] `POST /api/index/` — quality check → embed → upsert to Qdrant
- [ ] `POST /api/search/` — quality check → embed → Qdrant search → return matches
- [ ] Test with Postman / curl

### Phase 3 — Main service proxy *(~half day)*
- [ ] `POST /api/search/` in main_service: forward image → search_service → hydrate products from DB
- [ ] Auto-index on `ProductImage` save (signal or view logic)

### Phase 4 — Object detection crop *(~1–2 days)*
- [ ] YOLOv8 in search_service — crop largest detected object before embedding
- [ ] rembg background removal as optional preprocessing step
- [ ] Fallback to full image if no object detected

### Phase 5 — OOD filter *(~1 day)*
- [ ] Compute mean vector of indexed collection
- [ ] Reject query vectors with cosine distance > threshold from mean
- [ ] Return `{"error": "no similar products found"}` for out-of-distribution images

### Phase 6 — Polish *(demo day)*
- [ ] Grad-CAM heatmap overlay on search result (visualize what the model focused on)
- [ ] Admin page to bulk-index existing products
- [ ] Confidence threshold slider in frontend

---

## 14. Key Libraries

### main_service/requirements.txt
```
django>=4.2
djangorestframework
psycopg2-binary
Pillow
requests
python-dotenv
djangorestframework-simplejwt
```

### search_service/requirements.txt
```
django>=4.2
djangorestframework
torch
torchvision
transformers          # DINOv2
qdrant-client
Pillow
opencv-python-headless
rembg
ultralytics           # YOLOv8
python-dotenv
```

---

## 15. Notes & Decisions

| Decision | Rationale |
|----------|-----------|
| Local `MEDIA_ROOT` + Docker named volume | No S3 cost, shared between both services via same volume mount |
| `BytesIO` + `base64` thumbnail in DB | Eliminates need for extra media requests on list pages |
| DINOv2-base for MVP | Best zero-shot accuracy for product similarity, 768-dim |
| Cosine distance in Qdrant | DINOv2 outputs L2-normalized vectors; cosine = dot product, fast |
| Quality gate before indexing | Prevents blurry/dark images degrading search quality |
| Qdrant payload stores `product_id` only | Keeps Qdrant lean; full product data always fetched from Postgres |
| Single `docker-compose.yml` | Simpler for uni demo; split to separate compose files for "production" |
ALWAYS MARK THE TASKS AS DONE IN tasks.md IF YOU FINISHED THE TASK (THE MILESTONE ENTIRELY)