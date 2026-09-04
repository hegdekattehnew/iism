.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose -f infra/docker-compose.yml
VENV    := .venv
PY      := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn
ALEMBIC := $(VENV)/bin/alembic
PYTEST  := $(VENV)/bin/pytest
RUFF    := $(VENV)/bin/ruff
MYPY    := $(VENV)/bin/mypy
NODE_BIN := $(HOME)/.nvm/versions/node/v24.18.0/bin

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup
.PHONY: install
install: ## Create the venv and install api + web dependencies
	uv venv --python 3.12
	uv pip install -e ".[dev]"
	cd web && PATH="$(NODE_BIN):$$PATH" npm install

.PHONY: up
up: ## Start Postgres and Redis
	$(COMPOSE) up -d
	@echo "waiting for containers to report healthy..."
	@for i in $$(seq 1 30); do \
	  pg=$$(docker inspect --format='{{.State.Health.Status}}' iism-postgres-1 2>/dev/null); \
	  rd=$$(docker inspect --format='{{.State.Health.Status}}' iism-redis-1 2>/dev/null); \
	  if [ "$$pg" = healthy ] && [ "$$rd" = healthy ]; then echo "postgres: $$pg  redis: $$rd"; exit 0; fi; \
	  sleep 2; \
	done; echo "containers did not become healthy" >&2; exit 1

.PHONY: down
down: ## Stop containers (data volume is kept)
	$(COMPOSE) down

.PHONY: reset
reset: ## Stop containers AND destroy the data volume
	$(COMPOSE) down -v

# ---------------------------------------------------------------- database
.PHONY: migrate
migrate: ## Apply migrations
	$(ALEMBIC) upgrade head

.PHONY: migration
migration: ## Autogenerate a migration: make migration m="add courses"
	$(ALEMBIC) revision --autogenerate -m "$(m)"

.PHONY: seed
seed: ## Seed the taxonomy and marketplace inventory (idempotent)
	$(PY) scripts/seed_skills.py
	$(PY) scripts/seed_marketplace.py

.PHONY: mongosh
mongosh: ## Open a mongosh shell against the NSQF source
	docker exec -it iism-mongo-1 mongosh -u iism -p iism --authenticationDatabase admin nsqf

.PHONY: import-nsqf
import-nsqf: ## Project the NSQF corpus from MongoDB into PostgreSQL (idempotent)
	$(PY) scripts/import_nsqf.py

.PHONY: psql
psql: ## Open a psql shell in the container
	docker exec -it iism-postgres-1 psql -U iism -d iism

# ---------------------------------------------------------------- run
.PHONY: api
api: ## Run the API with reload (http://localhost:8000)
	$(UVICORN) api.main:app --reload --port 8000

.PHONY: worker
worker: ## Run the ARQ background worker
	$(VENV)/bin/arq api.core.tasks.WorkerSettings

.PHONY: web
web: ## Run the Next.js dev server (http://localhost:3000)
	cd web && PATH="$(NODE_BIN):$$PATH" npm run dev

.PHONY: gen-api
gen-api: ## Regenerate the TypeScript client from the live OpenAPI schema
	cd web && PATH="$(NODE_BIN):$$PATH" npm run gen:api

# ---------------------------------------------------------------- quality
.PHONY: test
test: ## Run the Python test suite (uses disposable containers)
	$(PYTEST) -q

.PHONY: lint
lint: ## Lint and type-check
	$(RUFF) check .
	$(RUFF) format --check .
	$(MYPY) api

.PHONY: fmt
fmt: ## Auto-format
	$(RUFF) check --fix .
	$(RUFF) format .

.PHONY: check
check: lint test ## Everything CI runs
