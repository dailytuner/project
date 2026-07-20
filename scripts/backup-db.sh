#!/bin/sh
set -e

DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups
PGHOST=postgres
PGUSER=postgres
PGPASSWORD=$(cat /run/secrets/postgrespassword 2>/dev/null || echo "")
export PGPASSWORD

echo "🔄 Starting backup at $(date)"

# Проверка подключения
if ! pg_isready -h $PGHOST -U $PGUSER; then
    echo "❌ Cannot connect to PostgreSQL"
    exit 1
fi

# Полный бэкап
pg_dumpall -h $PGHOST -U $PGUSER --clean --if-exists | gzip > ${BACKUP_DIR}/full-backup-${DATE}.sql.gz

# Бэкап только personalassistant
pg_dump -h $PGHOST -U $PGUSER personalassistant | gzip > ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz

# Проверка размера
SIZE=$(ls -lh ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz | awk '{print $5}')
echo "✅ Backup completed: ${SIZE}"

# Проверка целостности
pg_restore --list ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Backup integrity check passed"
else
    echo "❌ Backup integrity check FAILED"
    exit 1
fi

# Удалить старше 7 дней
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +7 -delete

# Уведомление в лог
echo "✅ Backup ${DATE} completed at $(date)"
