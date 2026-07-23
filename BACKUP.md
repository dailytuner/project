# 🗄️ Backup System

## Автоматические бэкапы

- **Время:** Ежедневно в 3:00
- **Хранение:** 7 дней
- **Формат:** gzip сжатие
- **Типы:** Полный + PersonalAssistant

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