# Restoring the databases

Three ways back, in order of what you should actually reach for.

## First: check whether anything is lost

A crashed **container** loses nothing. The data lives in Docker volumes, not in the containers, so
`make up` brings it back as it was. What loses data is deleting a volume — `docker compose down -v`,
a Docker Desktop factory reset, or pruning volumes.

```bash
docker volume ls | grep -E 'pgdata|mongo'   # still there? nothing to restore
```

## Path 1 — restore a dump  *(fastest, complete)*

Since Sprint 20 every dump is **encrypted** and written **outside the working tree**, to
`~/iism-backups` (override with `BACKUP_DIR=`). A dump holds real accounts — phone numbers, email
addresses, profiles — and a plaintext copy inside a project folder is one careless `zip`, sync or
screen-share from leaking all of them.

```bash
export IISM_BACKUP_PASSPHRASE='…'        # from the password manager; never commit it
make db-dump                             # Postgres -> ~/iism-backups/iism-pg-<stamp>.sql.gz.enc
make mongo-dump                          # MongoDB  -> ~/iism-backups/iism-mongo-<stamp>.archive.gz.enc

make db-restore    DUMP=~/iism-backups/iism-pg-<stamp>.sql.gz.enc        # INTO=iism by default
make mongo-restore DUMP=~/iism-backups/iism-mongo-<stamp>.archive.gz.enc # INTO=<db> to restore elsewhere
```

Encryption is `openssl enc -aes-256-cbc -pbkdf2 -iter 200000`, keyed from `IISM_BACKUP_PASSPHRASE`.
**Lose the passphrase and every dump made with it is unrecoverable** — that is the point, and the
reason it belongs in a password manager rather than a shell history. `db-restore` waits five
seconds before dropping its target, so a wrong `INTO=` can still be interrupted.

**MongoDB is now covered.** It is the source of record for the NSQF corpus (ADR-034), and until
Sprint 20 nothing backed it up: if it was lost, the taxonomy could not be rebuilt from anything in
this repository.

### The restore drill

A backup nobody has restored is not a backup. `make restore-drill` dumps both databases, restores
each into a scratch database (`iism_restore_drill`), compares them with the live ones, and drops the
scratch copies:

- Postgres: the table count, plus **exact** row counts for users, memberships, tenants, candidate
  profiles and skills, jobs, courses, skills and analytics events.
- MongoDB: `countDocuments` for every collection.
- It also checks the Postgres dump is not plaintext.

**Last run: 2026-09-11, passed.** Postgres 41 MB encrypted, 36 tables, key counts identical
(users 47, memberships 52, tenants 61, candidate_profiles 39, candidate_skills 90, jobs 23,
courses 21, skills 21,355, analytics_events 57). MongoDB 57 MB encrypted, 7 collections, every
count identical. Run it again after any change to the dump targets, and before trusting a new
machine's backups.

```bash
IISM_BACKUP_PASSPHRASE=… make restore-drill
```

**Dumps are not committed to git**, and no longer live in this directory at all.

> **An older plaintext dump may still be here.** `iism-20260907-1003.sql.gz` predates encryption
> and holds real accounts in the clear. It is gitignored, so it was never committed, but it is
> still on disk inside the project. Make an encrypted dump, then delete it.

## Path 2 — rebuild from source  *(no dump needed)*

```bash
make up && make migrate && make import-nsqf && make seed
```

Takes about two minutes and needs **MongoDB alive**, since the NSQF corpus is projected from it
(ADR-034). Almost every Postgres row is derived: the taxonomy, the hierarchy, the content layer,
the geography and the seeded marketplace are all reproducible.

What it does *not* bring back is people: user accounts, memberships, candidate profiles, consent
records and analytics events exist only in Postgres and only in a dump.

## Path 3 — schema only

`schema.sql` is the full DDL, **committed to git** and refreshed with:

```bash
make db-schema
```

Useful for reading the shape of the database, diffing it across commits, or creating an empty one
to migrate into. It contains no data.

## What is where

| | Rebuildable from |
|---|---|
| NSQF taxonomy, hierarchy, content, geography | MongoDB, via `make import-nsqf` |
| Marketplace inventory, demo candidates | `make seed` |
| **Users, profiles, consent, analytics events** | **nothing — Postgres dump only** |
| **The NSQF corpus itself** | **nothing — MongoDB dump only** |
