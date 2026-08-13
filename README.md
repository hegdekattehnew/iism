# Intelligent Integrated Skill Marketplace (IISM)

Workforce Mobility OS — marketplace + intelligence layer for skills, jobs, courses, and
career progression. India-first, single-sector MVP.

Architecture rationale: [docs/adr/architecture-decisions.md](docs/adr/architecture-decisions.md)
Working conventions for this repo: [CLAUDE.md](CLAUDE.md)

## Status

Repository skeleton only — folder structure and tooling in place per the ADR, no business
logic implemented yet. MVP feature scope is being defined next.

## Stack

Python 3.11 · FastAPI · PostgreSQL + pgvector · Redis · Celery

## Local setup

```bash
cp .env.example .env
docker compose up -d          # Postgres + Redis
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Health check: `curl http://localhost:8000/health`

## Tests

```bash
pytest
```
