# CloudOrbit developer tasks. Run `make help` for the list.
# Backend commands assume an activated virtualenv in backend/ and a reachable PostgreSQL
# (DATABASE_URL for the app, TEST_DATABASE_URL / PG_BIN_DIR / pgserver for tests).

.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend

.PHONY: help install dev-backend dev-frontend lint format test test-backend test-frontend migrate seed up down logs build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (dev) and frontend dependencies
	cd $(BACKEND) && pip install -r requirements-dev.txt && pip install -e . --no-deps
	cd $(FRONTEND) && npm ci

dev-backend: ## Run the API with auto-reload on :8000
	cd $(BACKEND) && uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run the Vite dev server on :5173 (proxies /api to :8000)
	cd $(FRONTEND) && npm run dev

lint: ## Ruff + ESLint + TypeScript type check
	cd $(BACKEND) && ruff check . && ruff format --check .
	cd $(FRONTEND) && npm run lint && npm run typecheck

format: ## Auto-format backend code
	cd $(BACKEND) && ruff check --fix . && ruff format .

test: test-backend test-frontend ## Run all tests

test-backend: ## Pytest with coverage (PostgreSQL required)
	cd $(BACKEND) && pytest --cov=app --cov-report=term

test-frontend: ## Vitest with coverage
	cd $(FRONTEND) && npm test -- --coverage

migrate: ## Apply database migrations
	cd $(BACKEND) && alembic upgrade head

seed: ## Load demo data via the mock providers (local only)
	cd $(BACKEND) && python -m app.seed

up: ## Start the Docker Compose stack
	docker compose up -d --build

down: ## Stop the Docker Compose stack
	docker compose down

logs: ## Tail Docker Compose logs
	docker compose logs -f --tail=100

build: ## Production frontend build + Docker images
	cd $(FRONTEND) && npm run build
	docker compose build

clean: ## Remove caches and build output
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.ruff_cache $(BACKEND)/htmlcov $(BACKEND)/.coverage $(FRONTEND)/dist $(FRONTEND)/coverage
