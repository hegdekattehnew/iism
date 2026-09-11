#!/usr/bin/env bash
# A backup nobody has restored is not a backup.
#
# Dumps Postgres and MongoDB through the real `make` targets -- encrypted, into
# $BACKUP_DIR -- restores each into a *scratch* database, compares what came
# back against the live data, and drops the scratch copies. Nothing live is
# touched. Exits non-zero on any mismatch.
#
#   IISM_BACKUP_PASSPHRASE=... make restore-drill
set -euo pipefail

PG=iism-postgres-1
MONGO=iism-mongo-1
PG_SCRATCH=iism_restore_drill
MONGO_SCRATCH=iism_restore_drill
MONGO_AUTH=(-u iism -p iism --authenticationDatabase admin --quiet)
cd "$(dirname "$0")/.."

echo "== dumping (encrypted) =="
PG_DUMP=$(make -s db-dump BACKUP_DIR="$BACKUP_DIR" | tail -1)
MONGO_DUMP=$(make -s mongo-dump BACKUP_DIR="$BACKUP_DIR" MONGO_DB="$MONGO_DB" | tail -1)
echo "  $PG_DUMP ($(du -h "$PG_DUMP" | cut -f1))"
echo "  $MONGO_DUMP ($(du -h "$MONGO_DUMP" | cut -f1))"

# The dump must not be readable as plain SQL or BSON: prove the encryption.
if head -c 64 "$PG_DUMP" | LC_ALL=C grep -q "PostgreSQL"; then
  echo "FAIL: Postgres dump is not encrypted"; exit 1
fi

cleanup() {
  docker exec "$PG" psql -U iism -d postgres -qc "DROP DATABASE IF EXISTS $PG_SCRATCH WITH (FORCE);" >/dev/null
  docker exec "$MONGO" mongosh "${MONGO_AUTH[@]}" "$MONGO_SCRATCH" --eval "db.dropDatabase()" >/dev/null
}
trap cleanup EXIT

echo "== restoring into scratch databases =="
make -s db-restore DUMP="$PG_DUMP" INTO="$PG_SCRATCH" >/dev/null
make -s mongo-restore DUMP="$MONGO_DUMP" INTO="$MONGO_SCRATCH" MONGO_DB="$MONGO_DB" >/dev/null

echo "== comparing Postgres, table by table =="
count_rows() {
  for table in users memberships tenants candidate_profiles candidate_skills jobs courses skills analytics_events; do
    echo "$table=$(docker exec "$PG" psql -U iism -d "$1" -Atc "select count(*) from $table")"
  done
}
LIVE_PG=$(count_rows iism)
DRILL_PG=$(count_rows "$PG_SCRATCH")
echo "$LIVE_PG" | tr '\n' ' '; echo
if [ "$LIVE_PG" != "$DRILL_PG" ]; then
  echo "FAIL: Postgres counts differ"; diff <(echo "$LIVE_PG") <(echo "$DRILL_PG"); exit 1
fi
TABLES_LIVE=$(docker exec "$PG" psql -U iism -d iism -Atc "select count(*) from information_schema.tables where table_schema='public'")
TABLES_DRILL=$(docker exec "$PG" psql -U iism -d "$PG_SCRATCH" -Atc "select count(*) from information_schema.tables where table_schema='public'")
[ "$TABLES_LIVE" = "$TABLES_DRILL" ] || { echo "FAIL: table count $TABLES_LIVE vs $TABLES_DRILL"; exit 1; }
echo "  Postgres OK: $TABLES_DRILL tables, key counts identical"

echo "== comparing MongoDB, collection by collection =="
count_docs() {
  docker exec "$MONGO" mongosh "${MONGO_AUTH[@]}" "$1" --eval '
    db.getCollectionNames().sort().forEach(c => print(c + "=" + db.getCollection(c).countDocuments()))'
}
LIVE_MONGO=$(count_docs "$MONGO_DB")
DRILL_MONGO=$(count_docs "$MONGO_SCRATCH")
if [ -z "$LIVE_MONGO" ] || [ "$LIVE_MONGO" != "$DRILL_MONGO" ]; then
  echo "FAIL: Mongo counts differ"; diff <(echo "$LIVE_MONGO") <(echo "$DRILL_MONGO"); exit 1
fi
echo "  Mongo OK: $(echo "$DRILL_MONGO" | wc -l | tr -d ' ') collections, every count identical"

echo "== drill passed $(date -u +%Y-%m-%dT%H:%MZ) =="
