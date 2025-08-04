#!/bin/bash
# Restore PostgreSQL database from a backup
# Usage: ./restore_postgres.sh <backup_file.sql.gz>
# Requires: psql, gunzip, and correct DB credentials in .env or environment

set -e
BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [[ -z "$DATABASE_URL" ]]; then
    echo "DATABASE_URL not set. Aborting."
    exit 1
fi

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

gunzip -c "$BACKUP_FILE" | psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DBNAME"

unset PGPASSWORD

echo "Restore complete."
