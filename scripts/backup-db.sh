#!/bin/sh
LOG_DIR="/var/log/backup"
mkdir -p $LOG_DIR
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
echo "========================================="

# Проверка подключения
if ! pg_isready -h $PGHOST -U $PGUSER; then
    echo "❌ Cannot connect to PostgreSQL"
    exit 1
fi

# Проверяем существование схемы psych
echo "🔍 Checking for psych schema..."
PSYCH_EXISTS=$(psql -h $PGHOST -U $PGUSER -d personalassistant -t -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'psych';" 2>/dev/null | tr -d ' ')

if [ -n "$PSYCH_EXISTS" ]; then
    echo "✅ Schema 'psych' exists"
    PSYCH_SCHEMA_FOUND=1
else
    echo "ℹ️  Schema 'psych' does not exist yet (will be created by init scripts)"
    PSYCH_SCHEMA_FOUND=0
fi

# ============================================
# 1. Полный бэкап всех баз
# ============================================
echo "📦 Creating full backup of all databases..."
pg_dumpall -h $PGHOST -U $PGUSER --clean --if-exists | gzip -9 > ${BACKUP_DIR}/full-backup-${DATE}.sql.gz

# Проверяем размер
FULL_SIZE=$(ls -lh ${BACKUP_DIR}/full-backup-${DATE}.sql.gz | awk '{print $5}')
echo "✅ Full backup created: ${FULL_SIZE}"

# ============================================
# 2. Бэкап базы personalassistant (основной)
# ============================================
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

# ============================================
# 3. Проверка целостности архива
# ============================================
echo "🔍 Verifying backup integrity..."
if gunzip -t ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz 2>/dev/null; then
    echo "✅ Archive integrity check passed"
else
    echo "❌ Archive integrity check FAILED"
    exit 1
fi

# ============================================
# 4. Проверка содержимого бэкапа
# ============================================
echo "🔍 Checking backup content..."

# Проверяем наличие схемы psych в бэкапе
PSYCH_IN_BACKUP=$(gunzip -c ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz 2>/dev/null | grep -c "CREATE SCHEMA psych" || echo 0)

if [ "$PSYCH_IN_BACKUP" -gt 0 ] || [ "$PSYCH_SCHEMA_FOUND" -eq 1 ]; then
    echo "✅ Schema 'psych' is included in backup"
else
    echo "⚠️  WARNING: Schema 'psych' NOT found in backup!"
    echo "⚠️  This is expected only if schema doesn't exist yet"
fi

# Считаем CREATE TABLE
TABLE_COUNT=$(gunzip -c ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz 2>/dev/null | grep -c "CREATE TABLE" || echo 0)
if [ "$TABLE_COUNT" -gt 0 ]; then
    echo "✅ Backup contains $TABLE_COUNT CREATE TABLE statements"
else
    echo "ℹ️  No CREATE TABLE found (database may be empty)"
fi

# Проверка данных
DATA_COUNT=$(gunzip -c ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz 2>/dev/null | grep -c "COPY" || echo 0)
if [ "$DATA_COUNT" -gt 0 ]; then
    echo "✅ Backup contains $DATA_COUNT COPY statements (data found)"
else
    echo "ℹ️  No COPY statements found (database may be empty)"
fi

# Подсчет таблиц в схеме psych
if [ "$PSYCH_SCHEMA_FOUND" -eq 1 ]; then
    PSYCH_TABLES=$(psql -h $PGHOST -U $PGUSER -d personalassistant -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'psych';" 2>/dev/null | tr -d ' ')
    echo "📊 Tables in psych schema: $PSYCH_TABLES"
fi

# ============================================
# 5. Создаем отдельный бэкап схемы psych (если существует)
# ============================================
if [ "$PSYCH_SCHEMA_FOUND" -eq 1 ]; then
    echo "📦 Creating separate psych schema backup..."
    pg_dump -h $PGHOST -U $PGUSER personalassistant \
        --schema=psych \
        --clean \
        --if-exists \
        | gzip -9 > ${BACKUP_DIR}/psych-schema-${DATE}.sql.gz
    
    PSYCH_SIZE=$(ls -lh ${BACKUP_DIR}/psych-schema-${DATE}.sql.gz | awk '{print $5}')
    echo "✅ Psych schema backup created: ${PSYCH_SIZE}"
    
    # Создаем симлинк на последний бэкап psych
    ln -sf psych-schema-${DATE}.sql.gz ${BACKUP_DIR}/psych-schema-latest.sql.gz
fi

# ============================================
# 6. Создаем симлинк на последний полный бэкап
# ============================================
ln -sf personalassistant-${DATE}.sql.gz ${BACKUP_DIR}/personalassistant-latest.sql.gz

# ============================================
# 7. Ротация (удалить старше 7 дней)
# ============================================
echo "🗑️  Rotating old backups..."
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +7 -delete 2>/dev/null || true
find ${BACKUP_DIR} -name "*.log" -mtime +30 -delete 2>/dev/null || true

# Подсчет оставшихся бэкапов
BACKUP_COUNT=$(find ${BACKUP_DIR} -name "personalassistant-*.sql.gz" -type f | wc -l)
echo "📊 Keeping ${BACKUP_COUNT} backups"

# ============================================
# 8. Сводка
# ============================================
echo "========================================="
echo "✅ Backup ${DATE} completed successfully"
echo "📊 Summary:"
echo "   - Full backup: full-backup-${DATE}.sql.gz (${FULL_SIZE})"
echo "   - Main backup: personalassistant-${DATE}.sql.gz (${SIZE})"
if [ "$PSYCH_SCHEMA_FOUND" -eq 1 ]; then
    echo "   - Psych schema: psych-schema-${DATE}.sql.gz (${PSYCH_SIZE})"
    echo "   - ✅ Schema 'psych' included and backed up separately"
else
    echo "   - ℹ️  Schema 'psych' not yet created"
fi
echo "   - Tables count: ${TABLE_COUNT}"
echo "   - Data COPY statements: ${DATA_COUNT}"
echo "========================================="

exit 0
