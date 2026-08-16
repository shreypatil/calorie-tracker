.PHONY: help install migrate migration seed dev api web test lint fmt reset logs docker-up docker-down

VENV := backend/.venv
PY   := $(VENV)/bin/python

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	cd backend && .venv/bin/pip install -e ".[dev]"
	@test -f backend/.env || cp backend/.env.example backend/.env
	cd frontend && npm install

migrate: ## Apply all database migrations
	cd backend && .venv/bin/alembic upgrade head

migration: ## Autogenerate a migration: make migration m="add x"
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(m)"

seed: ## Load the demo account and 30 days of data
	cd backend && .venv/bin/python -m scripts.seed

dev: migrate ## Run the API and the web app together (http://localhost:5173)
	@echo "API  → http://localhost:8000/docs"
	@echo "Web  → http://localhost:5173"
	@trap 'kill 0' INT TERM; \
	  (cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) & \
	  (cd frontend && npm run dev -- --host 0.0.0.0) & \
	  wait

api: migrate ## Run only the API, with auto-reload
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

web: ## Run only the web app (expects the API on port 8000)
	cd frontend && npm run dev

logs: ## Follow the JSON log file, pretty-printed if jq is available
	@mkdir -p backend/logs
	@touch backend/logs/app.log
	@if command -v jq >/dev/null 2>&1; then \
		tail -f backend/logs/app.log | jq -c '{t: .timestamp[11:19], lvl: .level, req: .request_id[0:8], msg: .message} + (del(.timestamp, .level, .logger, .message, .request_id))'; \
	else \
		echo "(install jq for readable output)"; tail -f backend/logs/app.log; \
	fi

test: ## Run the backend test suite and the frontend type check
	cd backend && .venv/bin/python -m pytest
	cd frontend && npm run build

lint: ## Check formatting and lint rules
	cd backend && .venv/bin/ruff check app tests scripts alembic && .venv/bin/ruff format --check app tests scripts alembic
	cd frontend && npm run lint

fmt: ## Apply formatting and auto-fixable lint rules
	cd backend && .venv/bin/ruff check --fix app tests scripts alembic && .venv/bin/ruff format app tests scripts alembic

reset: ## Delete the local database and rebuild it from migrations + seed
	rm -f backend/data/calorie_tracker.db*
	$(MAKE) migrate seed

docker-up: ## Build and run the whole stack on http://localhost:8080
	docker compose up --build

docker-down: ## Stop the Docker stack
	docker compose down
