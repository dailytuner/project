#!/bin/bash
# scripts/backup-monitor.sh

BACKUP_DIR="backups"
LOG_FILE="logs/backup-monitor.log"

echo "=== Backup Monitor $(date) ===" >> $LOG_FILE

# Проверка последнего бэкапа
LATEST=$(ls -t $BACKUP_DIR/*.sql.gz 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    AGE=$(( ($(date +%s) - $(stat -c %Y $LATEST)) / 3600 ))
    SIZE=$(stat -c %s $LATEST)
    echo "Latest backup: $(basename $LATEST)" >> $LOG_FILE
    echo "Age: $AGE hours" >> $LOG_FILE
    echo "Size: $SIZE bytes" >> $LOG_FILE

    if [ $AGE -gt 48 ]; then
        echo "⚠️  WARNING: Backup is older than 48 hours!" >> $LOG_FILE
    fi
    if [ $SIZE -lt 1000 ]; then
        echo "⚠️  WARNING: Backup is too small!" >> $LOG_FILE
    fi
else
    echo "❌ No backups found!" >> $LOG_FILE
fi

echo "---" >> $LOG_FILE