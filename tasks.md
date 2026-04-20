# Tasks

Legend: [ ] todo, [x] done

## M0 Infra
- [x] Create `docker-compose.yml` with `postgres`, `qdrant`, `main_service`, `search_service`, `nginx`
- [x] Scaffold both Django + DRF services
- [x] Configure env, DB, media volume, service URLs
- [x] Add `GET /api/health/` in `search_service`
- [x] Verify stack boots end-to-end

## M1 Users + Auth
- [ ] Create `users` app
- [ ] Add basic JWT auth
- [ ] Add registration, login, profile endpoints
- [ ] Protect user and order actions

## M2 Catalog + Media
- [ ] Create `Category`, `Product`, `ProductImage` models + migrations
- [ ] Add category and product CRUD endpoints
- [ ] Save uploads to `MEDIA_ROOT`
- [ ] Generate and store `thumbnail_b64` on image upload
- [ ] Return images and `thumbnail_b64` in product responses

## M3 Orders
- [ ] Create `Order` and `OrderItem` models + migrations
- [ ] Add order create, list, detail endpoints
- [ ] Link orders to authenticated users
- [ ] Snapshot product price on order create

## M4 Search Core
- [ ] Add DINOv2 embedder singleton
- [ ] Add image quality check
- [ ] Add Qdrant collection setup, upsert, search, delete helpers
- [ ] Implement `POST /api/index/`
- [ ] Implement `POST /api/search/`
- [ ] Implement `DELETE /api/index/<product_id>/`
- [ ] Smoke test index and search flow

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
