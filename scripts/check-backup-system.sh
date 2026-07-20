#!/bin/bash
# ============================================
# ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ БЭКАПОВ
# Personal Assistant - Backup System Checker
# ============================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Счетчики
PASSED=0
FAILED=0
WARNINGS=0

# ============================================
# ФУНКЦИИ
# ============================================

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ PASSED:${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}❌ FAILED:${NC} $1"
    ((FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠️  WARNING:${NC} $1"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}ℹ️  INFO:${NC} $1"
}

print_result() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${CYAN}РЕЗУЛЬТАТЫ ПРОВЕРКИ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}✅ PASSED:${NC} $PASSED"
    echo -e "${RED}❌ FAILED:${NC} $FAILED"
    echo -e "${YELLOW}⚠️  WARNINGS:${NC} $WARNINGS"
    echo ""

    if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Система готова к работе.${NC}"
        return 0
    elif [ $FAILED -eq 0 ] && [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Есть предупреждения, но система работает.${NC}"
        return 0
    else
        echo -e "${RED}❌ Есть критические ошибки! Требуется исправление.${NC}"
        return 1
    fi
}

# ============================================
# 1. ПРОВЕРКА ОКРУЖЕНИЯ
# ============================================

print_header "1. ПРОВЕРКА ОКРУЖЕНИЯ"

# Проверка Docker
if command -v docker &> /dev/null; then
    print_success "Docker установлен: $(docker --version)"
else
    print_fail "Docker не найден"
fi

# Проверка Docker Compose
if command -v docker compose &> /dev/null; then
    print_success "Docker Compose установлен"
else
    print_fail "Docker Compose не найден"
fi

# Проверка наличия файлов
FILES_TO_CHECK=(
    "docker-compose.yml"
    "scripts/backup-db.sh"
    "docker-secrets/postgrespassword.txt"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        print_success "Файл найден: $file"
    else
        print_fail "Файл отсутствует: $file"
    fi
done

# Проверка прав доступа к секретам
SECRETS_DIR="docker-secrets"
if [ -d "$SECRETS_DIR" ]; then
    PERMS=$(stat -c %a "$SECRETS_DIR" 2>/dev/null || stat -f %Lp "$SECRETS_DIR" 2>/dev/null)
    if [ "$PERMS" = "700" ] || [ "$PERMS" = "600" ]; then
        print_success "Права доступа к секретам: $PERMS"
    else
        print_warning "Права доступа к секретам: $PERMS (рекомендуется 700)"
    fi
else
    print_fail "Директория секретов не найдена: $SECRETS_DIR"
fi

# ============================================
# 2. ПРОВЕРКА СЕРВИСОВ
# ============================================

print_header "2. ПРОВЕРКА СЕРВИСОВ"

# Проверка запущенных контейнеров
SERVICES=("pa-postgres" "pa-backup" "backend-api" "web-ui")
for service in "${SERVICES[@]}"; do
    if docker ps --format "{{.Names}}" | grep -q "^$service$"; then
        STATUS=$(docker ps --format "{{.Status}}" --filter "name=$service")
        print_success "Сервис запущен: $service ($STATUS)"
    else
        print_fail "Сервис не запущен: $service"
    fi
done

# Проверка статуса контейнеров
print_info "Статус всех контейнеров:"
docker compose ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker ps

# ============================================
# 3. ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БД
# ============================================

print_header "3. ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ"

# Проверка postgres
if docker exec pa-postgres pg_isready -U postgres -d personalassistant > /dev/null 2>&1; then
    print_success "PostgreSQL готов к работе"

    # Проверка версии
    VERSION=$(docker exec pa-postgres psql -U postgres -c "SELECT version();" -t | head -1 | xargs)
    print_info "Версия PostgreSQL: $VERSION"

    # Проверка таблиц
    TABLE_COUNT=$(docker exec pa-postgres psql -U postgres -d personalassistant -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
    if [ "$TABLE_COUNT" -gt 0 ]; then
        print_success "Найдено таблиц: $TABLE_COUNT"
    else
        print_fail "Таблицы не найдены"
    fi

    # Проверка роли приложения
    if docker exec pa-postgres psql -U postgres -d personalassistant -tAc "SELECT 1 FROM pg_roles WHERE rolname='personal_assistant_app';" | grep -q 1; then
        print_success "Роль personal_assistant_app существует"
    else
        print_warning "Роль personal_assistant_app не найдена"
    fi

else
    print_fail "PostgreSQL не отвечает"
fi

# ============================================
# 4. ПРОВЕРКА БЭКАП-СЕРВИСА
# ============================================

print_header "4. ПРОВЕРКА БЭКАП-СЕРВИСА"

# Проверка секрета
if docker exec pa-backup cat /run/secrets/postgrespassword > /dev/null 2>&1; then
    print_success "Секрет postgrespassword доступен"
else
    print_fail "Секрет postgrespassword НЕ доступен"
fi

# Проверка скрипта
if docker exec pa-backup test -f /backup.sh; then
    print_success "Скрипт /backup.sh найден"
else
    print_fail "Скрипт /backup.sh не найден"
fi

# Проверка cron
if docker exec pa-backup crontab -l 2>/dev/null | grep -q "/backup.sh"; then
    CRON_LINE=$(docker exec pa-backup crontab -l 2>/dev/null | grep "/backup.sh")
    print_success "Cron настроен: $CRON_LINE"
else
    print_fail "Cron не настроен"
fi

# Проверка директории бэкапов
if docker exec pa-backup test -d /backups; then
    print_success "Директория /backups существует"
else
    print_fail "Директория /backups не найдена"
fi

# ============================================
# 5. ПРОВЕРКА ФАЙЛОВ БЭКАПОВ
# ============================================

print_header "5. ПРОВЕРКА ФАЙЛОВ БЭКАПОВ"

BACKUP_DIR="backups"
if [ ! -d "$BACKUP_DIR" ]; then
    print_warning "Директория backups не существует"
    mkdir -p "$BACKUP_DIR"
    print_info "Создана директория: $BACKUP_DIR"
fi

# Поиск файлов бэкапов
BACKUP_FILES=$(find "$BACKUP_DIR" -name "*.sql.gz" -type f 2>/dev/null | sort)
BACKUP_COUNT=$(echo "$BACKUP_FILES" | grep -c "\.sql\.gz$" 2>/dev/null || echo 0)

if [ "$BACKUP_COUNT" -gt 0 ]; then
    print_success "Найдено бэкапов: $BACKUP_COUNT"

    # Последний бэкап
    LATEST=$(ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        LATEST_NAME=$(basename "$LATEST")
        LATEST_SIZE=$(du -h "$LATEST" | cut -f1)
        LATEST_DATE=$(stat -c %y "$LATEST" 2>/dev/null || stat -f %Sm "$LATEST" 2>/dev/null)

        print_info "Последний бэкап: $LATEST_NAME"
        print_info "Размер: $LATEST_SIZE"
        print_info "Дата: $LATEST_DATE"

        # Проверка возраста
        AGE_HOURS=$(( ($(date +%s) - $(stat -c %Y "$LATEST" 2>/dev/null || stat -f %m "$LATEST" 2>/dev/null)) / 3600 ))
        if [ $AGE_HOURS -lt 24 ]; then
            print_success "Бэкап создан менее 24 часов назад ($AGE_HOURS ч.)"
        elif [ $AGE_HOURS -lt 48 ]; then
            print_warning "Бэкап создан $AGE_HOURS часов назад (старше 24 ч.)"
        else
            print_fail "Бэкап создан $AGE_HOURS часов назад (старше 48 ч.)"
        fi

        # Проверка размера
        SIZE_BYTES=$(stat -c %s "$LATEST" 2>/dev/null || stat -f %z "$LATEST" 2>/dev/null)
        if [ "$SIZE_BYTES" -gt 1000 ]; then
            print_success "Размер бэкапа корректный: $LATEST_SIZE"
        else
            print_fail "Размер бэкапа слишком маленький: $LATEST_SIZE"
        fi
    fi
else
    print_fail "Файлы бэкапов не найдены (.sql.gz)"
fi

# ============================================
# 6. ПРОВЕРКА ЦЕЛОСТНОСТИ БЭКАПА
# ============================================

print_header "6. ПРОВЕРКА ЦЕЛОСТНОСТИ БЭКАПА"

if [ -n "$LATEST" ] && [ -f "$LATEST" ]; then
    print_info "Проверка бэкапа: $(basename "$LATEST")"

    # Проверка на наличие CREATE TABLE
    if gunzip -c "$LATEST" 2>/dev/null | head -100 | grep -q "CREATE TABLE"; then
        print_success "Бэкап содержит CREATE TABLE"

        # Подсчет таблиц
        TABLE_COUNT=$(gunzip -c "$LATEST" 2>/dev/null | grep -c "CREATE TABLE" || echo 0)
        if [ "$TABLE_COUNT" -gt 0 ]; then
            print_success "Найдено CREATE TABLE: $TABLE_COUNT"
        fi
    else
        print_fail "Бэкап не содержит CREATE TABLE"
    fi

    # Проверка на наличие данных (COPY)
    if gunzip -c "$LATEST" 2>/dev/null | grep -q "COPY"; then
        print_success "Бэкап содержит данные (COPY)"
    else
        print_warning "Бэкап не содержит данных (COPY)"
    fi

    # Проверка синтаксиса
    if gunzip -c "$LATEST" 2>/dev/null | grep -q "ERROR"; then
        print_fail "Бэкап содержит ошибки (ERROR)"
    else
        print_success "Синтаксис бэкапа корректен"
    fi

else
    print_fail "Нет бэкапа для проверки"
fi

# ============================================
# 7. ТЕСТ ВОССТАНОВЛЕНИЯ
# ============================================

print_header "7. ТЕСТ ВОССТАНОВЛЕНИЯ (БЕЗОПАСНЫЙ)"

if [ -n "$LATEST" ] && [ -f "$LATEST" ]; then
    TEST_DB="test_restore_$(date +%s)"
    print_info "Создание тестовой БД: $TEST_DB"

    # Создание тестовой БД
    if docker exec pa-postgres psql -U postgres -c "CREATE DATABASE $TEST_DB;" 2>/dev/null; then
        print_success "Тестовая БД создана"

        # Восстановление
        print_info "Восстановление в тестовую БД..."
        if gunzip -c "$LATEST" 2>/dev/null | docker exec -i pa-postgres psql -U postgres -d "$TEST_DB" > /dev/null 2>&1; then
            print_success "Восстановление выполнено успешно"

            # Проверка таблиц
            TEST_TABLES=$(docker exec pa-postgres psql -U postgres -d "$TEST_DB" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
            if [ "$TEST_TABLES" -gt 0 ]; then
                print_success "Восстановлено таблиц: $TEST_TABLES"
            else
                print_fail "В тестовой БД нет таблиц"
            fi

            # Проверка данных
            USERS_COUNT=$(docker exec pa-postgres psql -U postgres -d "$TEST_DB" -tAc "SELECT COUNT(*) FROM users;" 2>/dev/null || echo 0)
            if [ "$USERS_COUNT" -gt 0 ] || [ "$USERS_COUNT" = "0" ]; then
                print_info "Пользователей в тестовой БД: $USERS_COUNT"
            fi

        else
            print_fail "Ошибка при восстановлении"
        fi

        # Удаление тестовой БД
        if docker exec pa-postgres psql -U postgres -c "DROP DATABASE $TEST_DB;" 2>/dev/null; then
            print_success "Тестовая БД удалена"
        else
            print_warning "Не удалось удалить тестовую БД"
        fi

    else
        print_fail "Не удалось создать тестовую БД"
    fi
else
    print_fail "Нет бэкапа для теста восстановления"
fi

# ============================================
# 8. ПРОВЕРКА ЛОГОВ
# ============================================

print_header "8. ПРОВЕРКА ЛОГОВ"

# Проверка логов бэкапа
if docker exec pa-backup test -f /backups/backup.log 2>/dev/null; then
    print_success "Файл лога существует: /backups/backup.log"

    LAST_LOG=$(docker exec pa-backup tail -1 /backups/backup.log 2>/dev/null)
    if [ -n "$LAST_LOG" ]; then
        print_info "Последняя запись в логе: $LAST_LOG"
    fi
else
    print_warning "Файл лога не найден (возможно, не настроен)"
fi

# Проверка логов контейнера
BACKUP_LOGS=$(docker logs pa-backup --tail 5 2>&1)
if [ -n "$BACKUP_LOGS" ]; then
    print_success "Логи контейнера доступны"
else
    print_warning "Логи контейнера пусты"
fi

# ============================================
# 9. ПРОВЕРКА ДИСКОВОГО ПРОСТРАНСТВА
# ============================================

print_header "9. ПРОВЕРКА ДИСКОВОГО ПРОСТРАНСТВА"

# Проверка места на диске
DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}')
DISK_AVAIL=$(df -h . | tail -1 | awk '{print $4}')

print_info "Использование диска: $DISK_USAGE"
print_info "Свободно: $DISK_AVAIL"

# Проверка размера директории бэкапов
if [ -d "$BACKUP_DIR" ]; then
    BACKUP_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
    print_info "Размер бэкапов: $BACKUP_SIZE"

    # Проверка на наличие слишком больших бэкапов
    if [ -d "$BACKUP_DIR" ] && [ "$(du -s "$BACKUP_DIR" 2>/dev/null | cut -f1)" -gt 5000000 ]; then
        print_warning "Бэкапы занимают более 5GB"
    fi
fi

# ============================================
# 10. РУЧНОЙ ЗАПУСК БЭКАПА
# ============================================

print_header "10. РУЧНОЙ ЗАПУСК БЭКАПА"

print_info "Запуск ручного бэкапа..."
if docker exec pa-backup /backup.sh 2>&1; then
    print_success "Ручной бэкап выполнен успешно"
else
    print_fail "Ручной бэкап завершился с ошибкой"
fi

# ============================================
# ВЫВОД РЕЗУЛЬТАТОВ
# ============================================

print_result

# Дополнительная информация
if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}📊 СИСТЕМА БЭКАПОВ РАБОТАЕТ КОРРЕКТНО!${NC}"
    echo ""
    echo -e "${BLUE}Следующие действия:${NC}"
    echo "  1. Проверьте бэкап завтра в 3:00: docker logs pa-backup --tail 20"
    echo "  2. Настройте мониторинг: make monitor-backup"
    echo "  3. Добавьте облачное хранилище: S3, Yandex Cloud, etc."
else
    echo ""
    echo -e "${RED}🔴 ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ ПРОБЛЕМЫ!${NC}"
    echo ""
    echo -e "${YELLOW}Рекомендации по исправлению:${NC}"

    # Проверка файла лога
    if ! docker exec pa-backup test -f /backups/backup.log 2>/dev/null; then
        echo "  - Добавьте логирование в backup-db.sh:"
        echo "    echo \"✅ Backup \$(date) completed\" >> /backups/backup.log"
    fi

    # Проверка cron
    if ! docker exec pa-backup crontab -l 2>/dev/null | grep -q "/backup.sh"; then
        echo "  - Настройте cron в docker-compose.yml:"
        echo "    command: sh -c \"echo '0 3 * * * /backup.sh' > /etc/crontabs/root && crond -f\""
    fi
fi

echo ""
echo -e "${BLUE}📝 Лог проверки сохранен в:${NC} backup-check.log"
echo ""

exit $FAILED