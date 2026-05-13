#!/bin/sh
DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups

# Бэкап всех БД
pg_dumpall -h postgres -U postgres --clean --if-exists | gzip > ${BACKUP_DIR}/full-backup-${DATE}.sql.gz

# Бэкап только personalassistant (быстрее)
pg_dump -h postgres -U postgres personalassistant | gzip > ${BACKUP_DIR}/personalassistant-${DATE}.sql.gz

# Удалить старше 7 дней
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +7 -delete

# S3 (опционально)
# aws s3 cp ${BACKUP_DIR}/*.sql.gz s3://pa-backups/ --recursive

echo "✅ Backup ${DATE} completed: $(ls -lh ${BACKUP_DIR}/*.sql.gz)"

