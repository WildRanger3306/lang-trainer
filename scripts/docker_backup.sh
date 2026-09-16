#!/bin/sh
# Daily full Postgres dump → zip in /backups.
# Env: PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE TZ KEEP_DAYS
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BASE="lang_trainer_${STAMP}"
SQL="${BACKUP_DIR}/${BASE}.sql"
ZIP="${BACKUP_DIR}/${BASE}.zip"

mkdir -p "$BACKUP_DIR"

echo "[backup] dumping ${PGDATABASE:-lang_trainer} @ $(date -Iseconds)"
pg_dump \
  --host="${PGHOST:-db}" \
  --port="${PGPORT:-5432}" \
  --username="${PGUSER:-lang}" \
  --dbname="${PGDATABASE:-lang_trainer}" \
  --no-owner \
  --no-acl \
  --file="$SQL"

echo "[backup] zipping → ${ZIP}"
zip -j -q "$ZIP" "$SQL"
rm -f "$SQL"

echo "[backup] done $(du -h "$ZIP" | cut -f1)"

# Drop zip archives older than KEEP_DAYS
if [ "$KEEP_DAYS" -gt 0 ] 2>/dev/null; then
  find "$BACKUP_DIR" -maxdepth 1 -type f -name 'lang_trainer_*.zip' -mtime +"$KEEP_DAYS" -print -delete \
    | while read -r f; do echo "[backup] removed old $f"; done || true
fi
