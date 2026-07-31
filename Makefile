.PHONY: up down backfill rebuild-web logs health dev-api dev-web

up:
	docker compose up -d --build

down:
	docker compose down

backfill:
	docker compose run --rm cron python -m thoracic.pipeline.backfill \
	  --from 2026-07-20 --to 2026-07-30 --concurrency 3

rebuild-web:
	cd web && npm ci && npm run build && cd ..
	docker compose restart web

logs:
	docker compose logs -f

health:
	curl -s http://localhost:8080/api/health | jq .

dev-api:
	cd api && uv run uvicorn src.thoracic.main:app --reload --port 8080

dev-web:
	cd web && npm run dev
