# Tasks

Legend: [ ] todo, [x] done

## M0 Infra
- [x] Create `docker-compose.yml` with `postgres`, `qdrant`, `main_service`, `search_service`, `nginx`
- [x] Scaffold both Django + DRF services
- [x] Configure env, DB, media volume, service URLs
- [x] Add `GET /api/health/` in `search_service`
- [x] Verify stack boots end-to-end

## M1 Users + Auth
- [x] Create `users` app
- [x] Add basic JWT auth
- [x] Add registration, login, profile endpoints
- [x] Protect user and order actions

## M2 Catalog + Media
- [x] Create `Category`, `Product`, `ProductImage` models + migrations
- [x] Add category and product CRUD endpoints
- [x] Save uploads to `MEDIA_ROOT`
- [x] Generate and store `thumbnail_b64` on image upload
- [x] Return images and `thumbnail_b64` in product responses

## M3 Orders
- [x] Create `Order` and `OrderItem` models + migrations
- [x] Add order create, list, detail endpoints
- [x] Link orders to authenticated users
- [x] Snapshot product price on order create

## M4 Search Core (complete)
- [x] Add DINOv2 embedder singleton
- [x] Add image quality check
- [x] Add Qdrant collection setup, upsert, search, delete helpers
- [x] Implement `POST /api/index/`
- [x] Implement `POST /api/search/`
- [x] Implement `DELETE /api/index/<product_id>/`
- [x] Smoke test index and search flow

## M5 Main Search Proxy
- [ ] Implement main `POST /api/search/` proxy to `search_service`
- [ ] Hydrate matched products from DB
- [ ] Attach similarity scores and sort descending
- [ ] Auto-index on `ProductImage` create
- [ ] Remove vectors on product or image delete

## M6 Search Preprocessing
- [ ] Add object detection crop before embedding
- [ ] Add optional `rembg` background removal
- [ ] Fallback to full image when no object detected
- [ ] Re-test search quality

## M7 OOD Filter
- [ ] Compute indexed collection mean vector
- [ ] Reject far query vectors by cosine threshold
- [ ] Return clear `no similar products found` response
- [ ] Tune threshold with sample queries

## M8 Admin + Demo Polish
- [ ] Add admin bulk-index action or page
- [ ] Add Grad-CAM heatmap overlay
- [ ] Add confidence threshold control in frontend
- [ ] Run final demo smoke test
