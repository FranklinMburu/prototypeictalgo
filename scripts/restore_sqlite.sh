#!/bin/bash
# Restore SQLite database from a backup
# Usage: ./restore_sqlite.sh <backup_file.db.gz> <restore_path>
# Example: ./restore_sqlite.sh ./db_backups/sqlite_backup_2025-08-03_12-00-00.db.gz ./ict_trading_system.db

set -e
BACKUP_FILE=$1
RESTORE_PATH=${2:-./ict_trading_system.db}
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.db.gz> <restore_path>"
    exit 1
fi

gunzip -c "$BACKUP_FILE" > "$RESTORE_PATH"

echo "Restore complete: $RESTORE_PATH"
