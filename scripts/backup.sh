#!/usr/bin/env sh
# Back up the database and the uploaded attachments, and prune old backups.
#
#   scripts/backup.sh
#
# Run on the server from the repo root, where docker-compose.yml and .env are.
# Daily from cron, before retention so a removal can still be undone from the
# previous night's copy:
#
#   15 2 * * * cd /srv/gabai && scripts/backup.sh >> backups/backup.log 2>&1
#   45 2 * * * docker exec gabai-api python -m app.retention --apply >> /srv/gabai/backups/retention.log 2>&1
#
# Restore (stop the api first so nothing writes mid-restore):
#
#   docker exec -i gabai-db pg_restore -U gabai -d gabai --clean --if-exists < backups/db-<stamp>.dump
#   tar -xzf backups/uploads-<stamp>.tar.gz -C backend
#
# A backup on the same disk survives a bad deploy, not a lost server. Copy
# BACKUP_DIR somewhere else too (another machine, or object storage).

set -eu

# Read single values from .env rather than sourcing it: it isn't shell, and a
# line like MAIL_FROM=GABAI <no-reply@...> would be run as a redirect.
env_value() {
    [ -f .env ] || return 0
    grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- \
        | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//"
}

POSTGRES_USER="${POSTGRES_USER:-$(env_value POSTGRES_USER)}"
POSTGRES_DB="${POSTGRES_DB:-$(env_value POSTGRES_DB)}"
BACKUP_DIR="${BACKUP_DIR:-$(env_value BACKUP_DIR)}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-$(env_value BACKUP_KEEP_DAYS)}"
POSTGRES_USER="${POSTGRES_USER:-gabai}"
POSTGRES_DB="${POSTGRES_DB:-gabai}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
# container_name in docker-compose.yml. By name, so this works whichever
# compose files the stack was started with.
DB_CONTAINER="${DB_CONTAINER:-gabai-db}"

stamp=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$BACKUP_DIR"

# Custom format: compressed, and pg_restore can restore one table from it.
# Written to a temp name first so a failed dump never looks like a good one.
db_file="$BACKUP_DIR/db-$stamp.dump"
docker exec "$DB_CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$db_file.part"
mv "$db_file.part" "$db_file"

uploads_file="$BACKUP_DIR/uploads-$stamp.tar.gz"
tar -czf "$uploads_file.part" -C backend uploads
mv "$uploads_file.part" "$uploads_file"

find "$BACKUP_DIR" -name 'db-*.dump' -mtime +"$BACKUP_KEEP_DAYS" -delete
find "$BACKUP_DIR" -name 'uploads-*.tar.gz' -mtime +"$BACKUP_KEEP_DAYS" -delete

echo "$stamp backed up: $(du -h "$db_file" | cut -f1) database, $(du -h "$uploads_file" | cut -f1) uploads"
