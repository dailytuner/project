#!/bin/bash
# ============================================
# АВТОМАТИЧЕСКОЕ ВОССТАНОВЛЕНИЕ БД ПРИ ЗАПУСКЕ
# ============================================

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Конфигурация
DB_HOST="postgres"
DB_USER="postgres"
DB_NAME="personalassistant"
BACKUP_DIR="/backups"
INIT_SCRIPT="/docker-entrypoint-initdb.d/init_db.sql"
FLAG_FILE="/tmp/.restore_completed"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🔄 SMART RESTORE SYSTEM v1.0${NC}"
echo -e "${BLUE}========================================${NC}"

# ============================================
# 1. ПОЛУЧЕНИЕ ПАРОЛЯ ИЗ СЕКРЕТА
# ============================================

# Docker Swarm автоматически монтирует секреты в /run/secrets/
if [ -f /run/secrets/postgrespassword ]; then
    export PGPASSWORD=$(cat /run/secrets/postgrespassword)
    echo -e "${GREEN}✅ Секрет загружен из /run/secrets/postgrespassword${NC}"
else
    echo -e "${RED}❌ Секрет не найден в /run/secrets/postgrespassword${NC}"
    echo -e "${YELLOW}⚠️  Доступные файлы в /run/secrets/:${NC}"
    ls -la /run/secrets/ 2>/dev/null || echo "Нет файлов"
    exit 1
fi

# ============================================
# 2. ПРОВЕРКА ФЛАГА
# ============================================

if [ -f "$FLAG_FILE" ] && [ "$(cat $FLAG_FILE)" = "$(date +%Y-%m-%d)" ]; then
    echo -e "${YELLOW}⚠️  Восстановление уже выполнено сегодня${NC}"
    echo -e "${GREEN}✅ Пропускаем (флаг: $(cat $FLAG_FILE))${NC}"
    exit 0
fi

# ============================================
# 3. ОЖИДАНИЕ ГОТОВНОСТИ POSTGRES
# ============================================

echo -e "${BLUE}⏳ Ожидание готовности PostgreSQL...${NC}"
MAX_RETRIES=30
RETRY=0

while ! pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ PostgreSQL не готов после $MAX_RETRIES попыток${NC}"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo ""
echo -e "${GREEN}✅ PostgreSQL готов${NC}"

# ============================================
# 4. ПРОВЕРКА СУЩЕСТВОВАНИЯ БД
# ============================================

echo -e "${BLUE}🔍 Проверка состояния базы данных...${NC}"

# Проверка существования БД
DB_EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" 2>/dev/null || echo 0)

if [ "$DB_EXISTS" = "1" ]; then
    # Проверка наличия таблиц
    TABLE_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo 0)
    echo -e "${BLUE}ℹ️  Найдено таблиц: $TABLE_COUNT${NC}"

    if [ "$TABLE_COUNT" -gt 0 ]; then
        # Проверка наличия данных в users
        USER_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM users;" 2>/dev/null || echo 0)
        echo -e "${BLUE}ℹ️  Пользователей: $USER_COUNT${NC}"

        if [ "$USER_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✅ База данных содержит данные (users: $USER_COUNT)${NC}"
            echo -e "${YELLOW}⚠️  Пропускаем восстановление${NC}"
            echo "$(date +%Y-%m-%d)" > "$FLAG_FILE"
            exit 0
        fi
    fi
fi

# ============================================
# 5. ПОИСК ПОСЛЕДНЕГО БЭКАПА
# ============================================

echo -e "${BLUE}🔍 Поиск последнего бэкапа...${NC}"

# Поиск в директории бэкапов
LATEST_BACKUP=$(ls -t $BACKUP_DIR/*.sql.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${YELLOW}⚠️  Бэкапы не найдены в $BACKUP_DIR${NC}"
    echo -e "${BLUE}ℹ️  Создаем новую базу из init_db.sql${NC}"

    # Проверяем существование init_db.sql
    if [ ! -f "$INIT_SCRIPT" ]; then
        echo -e "${RED}❌ init_db.sql не найден в $INIT_SCRIPT${NC}"
        exit 1
    fi

    # Создаем БД если не существует
    if [ "$DB_EXISTS" != "1" ]; then
        psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true
    fi

    # Выполняем инициализацию
    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$INIT_SCRIPT" 2>/dev/null; then
        echo -e "${GREEN}✅ База данных инициализирована из init_db.sql${NC}"
        echo "$(date +%Y-%m-%d)" > "$FLAG_FILE"
        exit 0
    else
        echo -e "${RED}❌ Ошибка инициализации${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Найден бэкап: $(basename $LATEST_BACKUP)${NC}"

# ============================================
# 6. ПРОВЕРКА ЦЕЛОСТНОСТИ БЭКАПА
# ============================================

echo -e "${BLUE}🔍 Проверка целостности бэкапа...${NC}"

if ! gunzip -t "$LATEST_BACKUP" 2>/dev/null; then
    echo -e "${RED}❌ Бэкап поврежден!${NC}"
    echo -e "${BLUE}ℹ️  Создаем новую базу из init_db.sql${NC}"

    if [ ! -f "$INIT_SCRIPT" ]; then
        echo -e "${RED}❌ init_db.sql не найден${NC}"
        exit 1
    fi

    psql -h "$DB_HOST" -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true

    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$INIT_SCRIPT" 2>/dev/null; then
        echo -e "${GREEN}✅ База данных инициализирована${NC}"
        echo "$(date +%Y-%m-%d)" > "$FLAG_FILE"
        exit 0
    else
        echo -e "${RED}❌ Ошибка инициализации${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Целостность бэкапа подтверждена${NC}"

# ============================================
# 7. ПРОСТОЕ ВОССТАНОВЛЕНИЕ
# ============================================

echo -e "${BLUE}🔄 Восстановление базы данных...${NC}"

# Создаем бэкап текущей БД (на всякий случай)
if [ "$DB_EXISTS" = "1" ]; then
    echo -e "${BLUE}ℹ️  Создание бэкапа текущей БД...${NC}"
    pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" | gzip > "/tmp/pre_restore_backup_$(date +%Y%m%d_%H%M%S).sql.gz" 2>/dev/null || true
fi

# Удаляем старую БД
echo -e "${BLUE}ℹ️  Удаление старой БД...${NC}"
psql -h "$DB_HOST" -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true

# Создаем новую БД
echo -e "${BLUE}ℹ️  Создание новой БД...${NC}"
psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true

# Восстанавливаем бэкап
echo -e "${BLUE}ℹ️  Восстановление из бэкапа...${NC}"
if gunzip -c "$LATEST_BACKUP" 2>/dev/null | psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Восстановление выполнено успешно${NC}"
else
    echo -e "${RED}❌ Ошибка восстановления${NC}"
    echo -e "${BLUE}ℹ️  Пробуем инициализацию из init_db.sql${NC}"

    if [ -f "$INIT_SCRIPT" ]; then
        psql -h "$DB_HOST" -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
        psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true

        if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$INIT_SCRIPT" 2>/dev/null; then
            echo -e "${GREEN}✅ База данных инициализирована из init_db.sql${NC}"
        else
            echo -e "${RED}❌ Ошибка инициализации${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ init_db.sql не найден${NC}"
        exit 1
    fi
fi

# ============================================
# 8. ПРИМЕНЕНИЕ НОВОЙ СТРУКТУРЫ (если нужно)
# ============================================

echo -e "${BLUE}🔍 Проверка актуальности структуры...${NC}"

# Проверяем наличие всех таблиц из init_db.sql
if [ -f "$INIT_SCRIPT" ]; then
    # Извлекаем имена таблиц из init_db.sql
    TABLES_IN_INIT=$(grep -i "CREATE TABLE IF NOT EXISTS" "$INIT_SCRIPT" | grep -oP 'CREATE TABLE IF NOT EXISTS \K\w+' | tr '\n' ' ')

    NEED_UPDATE=false
    for TABLE in $TABLES_IN_INIT; do
        EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='$TABLE';" 2>/dev/null || echo 0)
        if [ "$EXISTS" != "1" ]; then
            echo -e "${YELLOW}⚠️  Таблица '$TABLE' отсутствует${NC}"
            NEED_UPDATE=true
        fi
    done

    if [ "$NEED_UPDATE" = true ]; then
        echo -e "${YELLOW}⚠️  Обнаружены новые таблицы. Применяем обновления...${NC}"

        # Создаем временную БД с новой структурой
        TEMP_DB="temp_structure_$(date +%s)"
        psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $TEMP_DB;" 2>/dev/null || true

        # Применяем новую структуру
        psql -h "$DB_HOST" -U "$DB_USER" -d "$TEMP_DB" -f "$INIT_SCRIPT" 2>/dev/null || true

        # Извлекаем новые таблицы
        NEW_TABLES=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$TEMP_DB" -tAc "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name NOT IN (SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name IN (SELECT tablename FROM pg_tables WHERE schemaname='public'));")

        # Копируем новые таблицы в основную БД
        for TABLE in $NEW_TABLES; do
            echo -e "${BLUE}ℹ️  Добавление таблицы: $TABLE${NC}"
            psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "CREATE TABLE IF NOT EXISTS $TABLE AS SELECT * FROM $TEMP_DB.public.$TABLE;" 2>/dev/null || true
        done

        # Удаляем временную БД
        psql -h "$DB_HOST" -U "$DB_USER" -c "DROP DATABASE $TEMP_DB;" 2>/dev/null || true

        echo -e "${GREEN}✅ Структура обновлена${NC}"
    else
        echo -e "${GREEN}✅ Структура актуальна${NC}"
    fi
fi

# ============================================
# 9. ФИНАЛЬНАЯ ПРОВЕРКА
# ============================================

echo -e "${BLUE}🔍 Финальная проверка...${NC}"

FINAL_TABLE_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo 0)
FINAL_USER_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM users;" 2>/dev/null || echo 0)

echo -e "${GREEN}✅ Таблиц: $FINAL_TABLE_COUNT${NC}"
echo -e "${GREEN}✅ Пользователей: $FINAL_USER_COUNT${NC}"

if [ "$FINAL_TABLE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ База данных успешно восстановлена${NC}"
    echo "$(date +%Y-%m-%d)" > "$FLAG_FILE"
else
    echo -e "${RED}❌ База данных пуста!${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🎉 Восстановление завершено успешно!${NC}"
echo -e "${BLUE}========================================${NC}"

exit 0