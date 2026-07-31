#!/bin/bash
# ============================================
# ПОЛНАЯ ПРОВЕРКА СИСТЕМЫ БЭКАПОВ
# Personal Assistant - Backup System Checker
# ============================================

# НЕ ИСПОЛЬЗОВАТЬ set -e
# Вместо этого используем проверки вручную

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

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

# ============================================
# 2. ПРОВЕРКА СЕРВИСОВ
# ============================================

print_header "2. ПРОВЕРКА СЕРВИСОВ"

# Проверка запущенных контейнеров
SERVICES=("pa-postgres" "pa-backup" "project-backend-api-1" "pa-webui")
for service in "${SERVICES[@]}"; do
    if docker ps --format "{{.Names}}" 2>/dev/null | grep -q "^$service$"; then
        STATUS=$(docker ps --format "{{.Status}}" --filter "name=$service" 2>/dev/null)
        print_success "Сервис запущен: $service ($STATUS)"
    else
        print_fail "Сервис не запущен: $service"
    fi
done

# Проверка статуса контейнеров
print_info "Статус всех контейнеров:"
docker compose ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Не удалось получить статус"

# ============================================
# 3. ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БД
# ============================================

print_header "3. ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БАЗЕ ДАННЫХ"

# Проверка postgres
if docker exec pa-postgres pg_isready -U postgres -d personalassistant > /dev/null 2>&1; then
    print_success "PostgreSQL готов к работе"
    
    # Проверка таблиц
    TABLE_COUNT=$(docker exec pa-postgres psql -U postgres -d personalassistant -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo 0)
    if [ "$TABLE_COUNT" -gt 0 ]; then
        print_success "Найдено таблиц: $TABLE_COUNT"
    else
        print_fail "Таблицы не найдены"
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
if docker exec pa-backup test -f /backup.sh 2>/dev/null; then
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
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/*.sql.gz 2>/dev/null | wc -l)

if [ "$BACKUP_COUNT" -gt 0 ]; then
    print_success "Найдено бэкапов: $BACKUP_COUNT"
    
    # Последний бэкап
    LATEST=$(ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        LATEST_NAME=$(basename "$LATEST")
        LATEST_SIZE=$(du -h "$LATEST" 2>/dev/null | cut -f1)
        
        print_info "Последний бэкап: $LATEST_NAME"
        print_info "Размер: $LATEST_SIZE"
        
        # Проверка возраста
        AGE_HOURS=$(( ($(date +%s) - $(stat -c %Y "$LATEST" 2>/dev/null || stat -f %m "$LATEST" 2>/dev/null)) / 3600 ))
        if [ $AGE_HOURS -lt 24 ]; then
            print_success "Бэкап создан менее 24 часов назад ($AGE_HOURS ч.)"
        elif [ $AGE_HOURS -lt 48 ]; then
            print_warning "Бэкап создан $AGE_HOURS часов назад (старше 24 ч.)"
        else
            print_fail "Бэкап создан $AGE_HOURS часов назад (старше 48 ч.)"
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
    if gunzip -c "$LATEST" 2>/dev/null | grep -q "CREATE TABLE"; then
        print_success "Бэкап содержит CREATE TABLE"
        
        # Подсчет таблиц
        TABLE_COUNT=$(gunzip -c "$LATEST" 2>/dev/null | grep -c "CREATE TABLE" 2>/dev/null || echo 0)
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
    
    if docker exec pa-postgres psql -U postgres -c "CREATE DATABASE $TEST_DB;" 2>/dev/null; then
        print_success "Тестовая БД создана"
        
        print_info "Восстановление в тестовую БД..."
        if gunzip -c "$LATEST" 2>/dev/null | docker exec -i pa-postgres psql -U postgres -d "$TEST_DB" > /dev/null 2>&1; then
            print_success "Восстановление выполнено успешно"
            
            TEST_TABLES=$(docker exec pa-postgres psql -U postgres -d "$TEST_DB" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo 0)
            if [ "$TEST_TABLES" -gt 0 ]; then
                print_success "Восстановлено таблиц: $TEST_TABLES"
            else
                print_fail "В тестовой БД нет таблиц"
            fi
        else
            print_fail "Ошибка при восстановлении"
        fi
        
        docker exec pa-postgres psql -U postgres -c "DROP DATABASE $TEST_DB;" 2>/dev/null
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

# Проверка логов на хосте
if [ -f "logs/backup.log" ]; then
    print_success "Файл лога существует: logs/backup.log"
    LAST_LOG=$(tail -1 logs/backup.log 2>/dev/null)
    if [ -n "$LAST_LOG" ]; then
        print_info "Последняя запись в логе: $LAST_LOG"
    fi
else
    print_warning "Файл лога не найден: logs/backup.log"
fi

# ============================================
# 9. РЕЗУЛЬТАТЫ
# ============================================

print_result
