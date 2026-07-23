#!/bin/sh
exec 1> >(tee -a /backups/backup.log)
exec 2> >(tee -a /backups/backup_error.log >&2)

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
echo "📦 Creating full backup..."
pg_dumpall -h $PGHOST -U $PGUSER --clean --if-exists | gzip > ${BACKUP_DIR}/full-backup-${DATE}.sql.gz

# Бэкап только personalassistant
echo "📦 Creating personalassistant backup..."
pg_dump -h $PGHOST -U $PGUSER personalassistant | gzip -9 > ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz

# Проверка что файл создан
if [ ! -f ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz ]; then
    echo "❌ Backup file not created!"
    exit 1
fi

# Проверка размера
SIZE=$(ls -lh ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz | awk '{print $5}')
echo "✅ Backup created: ${SIZE}"

# Проверка целостности архива
echo "🔍 Verifying backup integrity..."
if gunzip -t ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz 2>/dev/null; then
    echo "✅ Archive integrity check passed"
else
    echo "❌ Archive integrity check FAILED"
    exit 1
fi

# Проверка содержимого
echo "🔍 Checking backup content..."
TABLE_COUNT=$(gunzip -c ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz 2>/dev/null | grep -c "CREATE TABLE" || echo 0)
if [ "$TABLE_COUNT" -gt 0 ]; then
    echo "✅ Backup contains $TABLE_COUNT CREATE TABLE statements"
else
    echo "⚠️  No CREATE TABLE found (database may be empty)"
fi

# Проверка данных
DATA_COUNT=$(gunzip -c ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz 2>/dev/null | grep -c "COPY" || echo 0)
if [ "$DATA_COUNT" -gt 0 ]; then
    echo "✅ Backup contains $DATA_COUNT COPY statements (data found)"
else
    echo "ℹ️  No COPY statements found (database may be empty)"
fi

# Ротация (удалить старше 7 дней)
BACKUP_COUNT=$(find ${BACKUP_DIR} -name "*.sql.gz" -type f | wc -l)
if [ $BACKUP_COUNT -gt 1 ]; then
    echo "🗑️  Removing backups older than 7 days..."
    find ${BACKUP_DIR} -name "*.sql.gz" -mtime +7 -delete
    echo "✅ Old backups removed"
else
    echo "⚠️  Only one backup exists, skipping rotation"
fi

echo "✅ Backup ${DATE} completed successfully at $(date)"
echo "📊 Summary: personalassistant-${DATE}.sql.gz (${SIZE}, ${TABLE_COUNT} tables)"
exit 0
