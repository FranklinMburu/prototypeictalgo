#!/bin/bash
# Automated SQLite backup script
# Usage: ./backup_sqlite.sh <db_path> <backup_dir>
# Example: ./backup_sqlite.sh ./ict_trading_system.db ./db_backups

set -e
DB_PATH=${1:-./ict_trading_system.db}
BACKUP_DIR=${2:-./db_backups}
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
FILENAME="sqlite_backup_$DATE.db.gz"

mkdir -p "$BACKUP_DIR"

gzip -c "$DB_PATH" > "$BACKUP_DIR/$FILENAME"

echo "Backup complete: $BACKUP_DIR/$FILENAME"
