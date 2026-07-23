# 🗄️ Backup System

## Автоматические бэкапы

- **Время:** Ежедневно в 3:00
- **Хранение:** 7 дней
- **Формат:** gzip сжатие
- **Типы:** Полный + PersonalAssistant

# Сделать все .sh файлы в scripts/ исполняемыми
chmod +x scripts/*.sh
chmod +x scripts/backup-db.sh
chmod +x scripts/restore-on-start.sh
chmod +x scripts/check-backup-system.sh
chmod +x scripts/restore-db.sh
chmod +x scripts/backup-monitor.sh
chmod +x scripts/first-deploy.sh
chmod +x scripts/init-caches.sh

## Команды

```bash
# Ручной бэкап
make backup

# Проверка статуса
make check-backup

# Проверка целостности
make verify-backup

# Восстановление
make restore-latest

# Список бэкапов
make restore-list
Основные:
make status          # Статус всех сервисов
make backup          # Ручной бэкап
make check-backup    # Проверка бэкапов
make verify-backup   # Проверка целостности
./scripts/check-backup-system.sh  # Полная проверка
Восстановление:
make restore-list    # Список бэкапов
make restore-latest  # Восстановить последний
make restore-file    # Восстановить конкретный
Логи:
docker logs pa-backup -f           # Логи контейнера
docker exec pa-backup cat /backups/backup.log  # Лог бэкапов
make logs-backup                    # Через Makefile
Управление:
docker compose down                 # Остановить (БД сохраняется)
docker compose up -d                # Запустить
make clean                          # Полная очистка (ОСТОРОЖНО!)
