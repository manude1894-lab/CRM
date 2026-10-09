#!/usr/bin/env sh
# Daily database backup for the Triam CRM.
#
#   DATABASE_URL=postgresql://user:pass@host:port/db  BACKUP_DIR=/backups  sh scripts/backup_db.sh
#
# Writes BACKUP_DIR/daily/triam-crm-YYYY-MM-DD.sql.gz and, on Saturdays, a copy in
# BACKUP_DIR/weekly/ (the "weekend data retained without overwriting" from the BRD discussion).
# Keeps the last 14 daily and 8 weekly backups. Needs pg_dump (PostgreSQL client tools, same
# major version as the server: 16).
#
# Restore into an EMPTY database:
#   gunzip -c triam-crm-YYYY-MM-DD.sql.gz | psql "$TARGET_DATABASE_URL"
set -eu

: "${DATABASE_URL:?Set DATABASE_URL to the CRM database}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DAILY_KEEP="${DAILY_KEEP:-14}"
WEEKLY_KEEP="${WEEKLY_KEEP:-8}"

# SQLAlchemy-style URLs (postgresql+psycopg2://) are not understood by pg_dump.
URL=$(printf '%s' "$DATABASE_URL" | sed 's#^postgresql+[a-z0-9]*://#postgresql://#')
STAMP=$(date +%Y-%m-%d)
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
FILE="$BACKUP_DIR/daily/triam-crm-$STAMP.sql.gz"

pg_dump --no-owner --no-privileges "$URL" | gzip -9 > "$FILE.tmp"
mv "$FILE.tmp" "$FILE"
echo "Backup written: $FILE ($(du -h "$FILE" | cut -f1))"

if [ "$(date +%u)" = "6" ]; then
  cp "$FILE" "$BACKUP_DIR/weekly/"
  echo "Weekly copy kept: $BACKUP_DIR/weekly/$(basename "$FILE")"
fi

# Retention: newest first, delete beyond the limits.
ls -1t "$BACKUP_DIR"/daily/triam-crm-*.sql.gz 2>/dev/null | tail -n +"$((DAILY_KEEP + 1))" | xargs -r rm -f
ls -1t "$BACKUP_DIR"/weekly/triam-crm-*.sql.gz 2>/dev/null | tail -n +"$((WEEKLY_KEEP + 1))" | xargs -r rm -f
