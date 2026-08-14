# Intelligent Integrated Skill Marketplace (IISM)

Workforce Mobility OS — marketplace + intelligence layer for skills, jobs, courses, and
career progression. India-first, single-sector MVP.

Architecture rationale: [docs/adr/architecture-decisions.md](docs/adr/architecture-decisions.md)
Working conventions for this repo: [CLAUDE.md](CLAUDE.md)

## Status

Identity module implemented: authentication (email/password + Google OAuth, JWT
access/refresh, email verification, password reset) and registration for all actor types
(Candidate, Employer, Course Provider, Assessment Provider, Government Agency, Platform Admin,
Super Admin), plus CSV bulk upload and API-key based external intake for candidates. Other
modules are still skeletons. MVP feature scope beyond identity is being defined next.

## Stack

Python 3.11 · FastAPI · PostgreSQL + pgvector · Redis · Celery

## Local setup

```bash
cp .env.example .env
docker compose up -d          # Postgres + Redis
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Health check: `curl http://localhost:8000/health`

### Bootstrapping the first Super Admin

`/admin/staff` (for creating more platform staff) requires an existing super admin, so the
first one must be created directly against the database:

```bash
python scripts/create_superuser.py
```

## Tests

```bash
pytest
```
