#!/bin/bash
# Automated PostgreSQL backup script
# Usage: ./backup_postgres.sh <backup_dir>
# Requires: pg_dump, gzip, and correct DB credentials in .env or environment

set -e
BACKUP_DIR=${1:-./db_backups}
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
FILENAME="postgres_backup_$DATE.sql.gz"

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

mkdir -p "$BACKUP_DIR"

if [[ -z "$DATABASE_URL" ]]; then
    echo "DATABASE_URL not set. Aborting."
    exit 1
fi

# Parse DB connection info from DATABASE_URL
echo "$DATABASE_URL" | grep -q 'postgres' || { echo "Not a PostgreSQL DATABASE_URL"; exit 1; }

# Extract credentials
PROTO=$(echo $DATABASE_URL | cut -d':' -f1)
USERPASS_HOSTPORT_DB=$(echo $DATABASE_URL | cut -d'/' -f3-)
USERPASS_HOSTPORT=$(echo $USERPASS_HOSTPORT_DB | cut -d'/' -f1)
DBNAME=$(echo $USERPASS_HOSTPORT_DB | cut -d'/' -f2 | cut -d'?' -f1)
USER=$(echo $USERPASS_HOSTPORT | cut -d':' -f1)
PASS_HOSTPORT=$(echo $USERPASS_HOSTPORT | cut -d':' -f2-)
PASS=$(echo $PASS_HOSTPORT | cut -d'@' -f1)
HOSTPORT=$(echo $PASS_HOSTPORT | cut -d'@' -f2)
HOST=$(echo $HOSTPORT | cut -d':' -f1)
PORT=$(echo $HOSTPORT | cut -d':' -f2)

export PGPASSWORD="$PASS"

pg_dump -h "$HOST" -p "$PORT" -U "$USER" -F p "$DBNAME" | gzip > "$BACKUP_DIR/$FILENAME"

unset PGPASSWORD

echo "Backup complete: $BACKUP_DIR/$FILENAME"
