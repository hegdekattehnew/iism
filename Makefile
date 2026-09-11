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
seed: ## Seed the taxonomy, marketplace inventory and demo candidates (idempotent)
	$(NO_TIMEOUT) $(PY) scripts/seed_skills.py
	$(NO_TIMEOUT) $(PY) scripts/seed_marketplace.py
	$(NO_TIMEOUT) $(PY) scripts/seed_candidates.py

.PHONY: evaluate
evaluate: ## Score the matcher against the hand-labelled golden set
	$(NO_TIMEOUT) $(PY) scripts/evaluate_matching.py

# ---------------------------------------------------------------- backup
# Operator scripts share the app's database engine, which now carries a
# statement timeout. The importer and the seed run legitimately long statements.
NO_TIMEOUT := DB_STATEMENT_TIMEOUT_MS=0

PG := iism-postgres-1
MONGO := iism-mongo-1
MONGO_DB ?= iism_nsqf_master_data
# Outside the working tree, and encrypted. Dumps used to land in backups/ inside
# the repository -- gitignored, but a full dump holds real users' phones and
# profiles, and one `git add -f` or one careless zip away from leaving the
# machine. The passphrase comes from the environment and is never stored here.
BACKUP_DIR ?= $(HOME)/iism-backups
STAMP := $(shell date +%Y%m%d-%H%M%S)
ENCRYPT := openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:IISM_BACKUP_PASSPHRASE
DECRYPT := openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:IISM_BACKUP_PASSPHRASE
REQUIRE_PASSPHRASE = @test -n "$$IISM_BACKUP_PASSPHRASE" || { echo "Set IISM_BACKUP_PASSPHRASE first -- dumps are encrypted."; exit 1; }

.PHONY: db-schema
db-schema: ## Refresh backups/schema.sql (DDL only, committed to git)
	@docker exec $(PG) pg_dump -U iism -d iism --schema-only --no-owner --no-privileges \
	  > backups/schema.sql
	@echo "backups/schema.sql  $$(wc -c < backups/schema.sql | tr -d ' ') bytes"

.PHONY: db-dump
db-dump: ## Encrypted full Postgres dump to $(BACKUP_DIR) (needs IISM_BACKUP_PASSPHRASE)
	$(REQUIRE_PASSPHRASE)
	@mkdir -p $(BACKUP_DIR) && chmod 700 $(BACKUP_DIR)
	@docker exec $(PG) pg_dump -U iism -d iism --no-owner --no-privileges \
	  | gzip -c | $(ENCRYPT) > $(BACKUP_DIR)/iism-pg-$(STAMP).sql.gz.enc
	@echo "$(BACKUP_DIR)/iism-pg-$(STAMP).sql.gz.enc"

.PHONY: db-restore
db-restore: ## Restore Postgres: make db-restore DUMP=... [INTO=iism] (DROPS the target)
	$(REQUIRE_PASSPHRASE)
	@test -f "$(DUMP)" || { echo "No such dump: $(DUMP)"; exit 1; }
	@echo "This DROPS and recreates database '$(or $(INTO),iism)'. Ctrl-C within 5s to abort."
	@sleep 5
	@docker exec $(PG) psql -U iism -d postgres -c "DROP DATABASE IF EXISTS $(or $(INTO),iism) WITH (FORCE);"
	@docker exec $(PG) psql -U iism -d postgres -c "CREATE DATABASE $(or $(INTO),iism);"
	@$(DECRYPT) < $(DUMP) | gunzip -c \
	  | docker exec -i $(PG) psql -U iism -d $(or $(INTO),iism) -v ON_ERROR_STOP=1 -q
	@echo "restored $(DUMP) into $(or $(INTO),iism)"

.PHONY: mongo-dump
mongo-dump: ## Encrypted dump of the NSQF source of record to $(BACKUP_DIR)
	$(REQUIRE_PASSPHRASE)
	@mkdir -p $(BACKUP_DIR) && chmod 700 $(BACKUP_DIR)
	@docker exec $(MONGO) mongodump -u iism -p iism --authenticationDatabase admin \
	  --db $(MONGO_DB) --archive --gzip --quiet \
	  | $(ENCRYPT) > $(BACKUP_DIR)/iism-mongo-$(STAMP).archive.gz.enc
	@echo "$(BACKUP_DIR)/iism-mongo-$(STAMP).archive.gz.enc"

.PHONY: mongo-restore
mongo-restore: ## Restore Mongo: make mongo-restore DUMP=... [INTO=<db>] (replaces INTO)
	$(REQUIRE_PASSPHRASE)
	@test -f "$(DUMP)" || { echo "No such dump: $(DUMP)"; exit 1; }
	@$(DECRYPT) < $(DUMP) | docker exec -i $(MONGO) mongorestore -u iism -p iism \
	  --authenticationDatabase admin --archive --gzip --drop --quiet \
	  --nsFrom '$(MONGO_DB).*' --nsTo '$(or $(INTO),$(MONGO_DB)).*'
	@echo "restored $(DUMP) into $(or $(INTO),$(MONGO_DB))"

.PHONY: restore-drill
restore-drill: ## Prove both backups restore: dump, restore into scratch, compare, clean up
	$(REQUIRE_PASSPHRASE)
	@BACKUP_DIR=$(BACKUP_DIR) MONGO_DB=$(MONGO_DB) scripts/restore_drill.sh

.PHONY: mongosh
mongosh: ## Open a mongosh shell against the NSQF source
	docker exec -it iism-mongo-1 mongosh -u iism -p iism --authenticationDatabase admin nsqf

.PHONY: import-nsqf
import-nsqf: ## Project the NSQF corpus from MongoDB into PostgreSQL (idempotent)
	$(NO_TIMEOUT) $(PY) scripts/import_nsqf.py

.PHONY: psql
psql: ## Open a psql shell in the container
	docker exec -it iism-postgres-1 psql -U iism -d iism

# ---------------------------------------------------------------- run
.PHONY: api
api: ## Run the API with reload (http://localhost:8000)
	$(UVICORN) api.main:app --reload --port 8000

.PHONY: worker
worker: ## Run the ARQ background worker
	# api.worker, not api.core.tasks: arq runs its own dictConfig *after*
	# importing the settings module, so logging has to be configured from
	# on_startup or every worker line is emitted twice.
	$(VENV)/bin/arq --custom-log-dict api.worker.LOG_CONFIG api.worker.WorkerSettings

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
