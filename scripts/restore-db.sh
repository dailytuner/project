#!/bin/bash
# scripts/restore-db.sh
# Использование: ./restore-db.sh [backup_file]

set -e

BACKUP_FILE=${1:-$(ls -t backups/*.sql.gz | head -1)}
PGHOST=postgres
PGUSER=postgres

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "🔄 Restoring from: $BACKUP_FILE"
echo "⚠️  This will DROP all existing data!"
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Restore cancelled"
    exit 1
fi

# Получаем пароль
PGPASSWORD=$(cat docker-secrets/postgrespassword.txt)
export PGPASSWORD

# Восстановление
gunzip -c $BACKUP_FILE | psql -h $PGHOST -U $PGUSER -d personalassistant

echo "✅ Restore completed from: $BACKUP_FILE"