# Restoring the database

Three ways back, in order of what you should actually reach for.

## First: check whether anything is lost

A crashed **container** loses nothing. The data lives in the `pgdata` Docker volume, not in the
container, so `make up` brings it back as it was. What loses data is deleting the volume —
`docker compose down -v`, a Docker Desktop factory reset, or pruning volumes.

```bash
docker volume ls | grep pgdata          # still there? nothing to restore
```

## Path 1 — restore a dump  *(fastest, complete)*

```bash
make db-dump                                        # ~8s, writes backups/iism-<stamp>.sql.gz
make db-restore DUMP=backups/iism-20260907-1003.sql.gz
```

About **40 MB gzipped**, restores in about five seconds, and brings back everything: 36 tables,
140 indexes, the `pgvector` and `pg_trgm` extensions, the `GENERATED` tsvector columns, and all
716,000 rows. Verified by restoring into a scratch database and comparing row counts table by
table — a backup nobody has restored is not a backup.

**Dumps are not committed to git.** Forty megabytes of regenerable data per snapshot would bloat
the repository permanently, and the schema below plus the source data reproduce it.

## Path 2 — rebuild from source  *(no dump needed)*

```bash
make up && make migrate && make import-nsqf && make seed
```

Takes about two minutes and needs **MongoDB alive**, since the NSQF corpus is projected from it
(ADR-034). This is the honest default for this project, because **716,187 of 716,257 rows are
derived**: the taxonomy, the hierarchy, the content layer, the geography and the seeded
marketplace are all reproducible.

What it does *not* bring back is the other 70 rows — real user accounts, candidate profiles and
analytics events. Those exist only in Postgres and only in a dump. Today that is 14 sign-ins and
a handful of events; the day it is not, Path 1 stops being optional.

## Path 3 — schema only

`schema.sql` is the full DDL, about 61 KB, **committed to git** and refreshed with:

```bash
make db-schema
```

Useful for reading the shape of the database, diffing it across commits, or creating an empty one
to migrate into. It contains no data.

## What is where

| | Rows | Rebuildable from |
|---|---|---|
| NSQF taxonomy, hierarchy, content | ~700,000 | MongoDB, via `make import-nsqf` |
| Geography | ~7,900 | MongoDB |
| Marketplace inventory, demo candidates | ~250 | `make seed` |
| **Users, profiles, analytics events** | **70** | **nothing — dump only** |

MongoDB itself is the source of record for the corpus and is *not* covered by any of this. If it
is lost, the taxonomy cannot be rebuilt from anything in this repository.
