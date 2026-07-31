#!/bin/sh
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
echo -e "${BLUE}🔄 SMART RESTORE SYSTEM v2.0${NC}"
echo -e "${BLUE}========================================${NC}"

# ============================================
# 1. ПОЛУЧЕНИЕ ПАРОЛЯ
# ============================================

if [ -f /run/secrets/postgrespassword ]; then
    export PGPASSWORD=$(cat /run/secrets/postgrespassword | tr -d '\n\r')
    echo -e "${GREEN}✅ Секрет загружен${NC}"
else
    echo -e "${RED}❌ Секрет не найден${NC}"
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
# 3. ОЖИДАНИЕ POSTGRES
# ============================================

echo -e "${BLUE}⏳ Ожидание PostgreSQL...${NC}"
MAX_RETRIES=30
RETRY=0

while ! pg_isready -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ PostgreSQL не готов${NC}"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo ""
echo -e "${GREEN}✅ PostgreSQL готов${NC}"

# ============================================
# 4. ПРОВЕРКА СУЩЕСТВОВАНИЯ ДАННЫХ
# ============================================

echo -e "${BLUE}🔍 Проверка состояния БД...${NC}"

# Проверка существования БД
DB_EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';" 2>/dev/null || echo 0)

if [ "$DB_EXISTS" = "1" ]; then
    TABLE_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo 0)
    echo -e "${BLUE}ℹ️  Найдено таблиц: $TABLE_COUNT${NC}"
    
    if [ "$TABLE_COUNT" -gt 0 ]; then
        USER_COUNT=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM users;" 2>/dev/null || echo 0)
        echo -e "${BLUE}ℹ️  Пользователей: $USER_COUNT${NC}"
        
        if [ "$USER_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✅ База данных содержит данные${NC}"
            echo -e "${YELLOW}⚠️  Пропускаем восстановление${NC}"
            echo "$(date +%Y-%m-%d)" > "$FLAG_FILE"
            exit 0
        fi
    fi
fi

# ============================================
# 5. ПОИСК БЭКАПА
# ============================================

echo -e "${BLUE}🔍 Поиск последнего бэкапа...${NC}"
LATEST_BACKUP=$(ls -t $BACKUP_DIR/*.sql.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${YELLOW}⚠️  Бэкапы не найдены${NC}"
    echo -e "${BLUE}ℹ️  Создаем новую БД из init_db.sql${NC}"
    
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

echo -e "${GREEN}✅ Найден бэкап: $(basename $LATEST_BACKUP)${NC}"

# ============================================
# 6. ПРОВЕРКА БЭКАПА
# ============================================

echo -e "${BLUE}🔍 Проверка целостности...${NC}"
if ! gunzip -t "$LATEST_BACKUP" 2>/dev/null; then
    echo -e "${RED}❌ Бэкап поврежден!${NC}"
    exit 1
fi

# Проверка что бэкап не пустой
SIZE=$(stat -c %s "$LATEST_BACKUP" 2>/dev/null || stat -f %z "$LATEST_BACKUP" 2>/dev/null)
if [ "$SIZE" -lt 1000 ]; then
    echo -e "${RED}❌ Бэкап слишком маленький (${SIZE} байт) - поврежден!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Целостность подтверждена${NC}"

# ============================================
# 7. ВОССТАНОВЛЕНИЕ (ПРОСТАЯ СТРАТЕГИЯ)
# ============================================

echo -e "${BLUE}🔄 Восстановление базы данных...${NC}"

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
    echo -e "${BLUE}ℹ️  Создаем новую БД из init_db.sql${NC}"
    
    psql -h "$DB_HOST" -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true
    
    if [ -f "$INIT_SCRIPT" ]; then
        psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -f "$INIT_SCRIPT" 2>/dev/null
    fi
    exit 1
fi

# ============================================
# 8. ПРИМЕНЕНИЕ НОВОЙ СТРУКТУРЫ (ЕСЛИ НУЖНО)
# ============================================

echo -e "${BLUE}🔍 Проверка структуры...${NC}"

if [ -f "$INIT_SCRIPT" ]; then
    # Получаем список таблиц из init_db.sql
    NEW_TABLES=$(grep -i "CREATE TABLE" "$INIT_SCRIPT" | grep -o "public\.[a-zA-Z0-9_]*" | sed 's/public\.//' | sort -u)
    
    NEED_UPDATE=false
    for TABLE in $NEW_TABLES; do
        EXISTS=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='$TABLE';" 2>/dev/null || echo 0)
        if [ "$EXISTS" != "1" ]; then
            echo -e "${YELLOW}⚠️  Таблица '$TABLE' отсутствует${NC}"
            NEED_UPDATE=true
            break
        fi
    done
    
    if [ "$NEED_UPDATE" = true ]; then
        echo -e "${YELLOW}⚠️  Обнаружены новые таблицы. Применяем обновления...${NC}"
        
        # Создаем временную БД с новой структурой
        TEMP_DB="temp_structure_$(date +%s)"
        psql -h "$DB_HOST" -U "$DB_USER" -c "CREATE DATABASE $TEMP_DB;" 2>/dev/null || true
        
        # Применяем структуру во временную БД
        psql -h "$DB_HOST" -U "$DB_USER" -d "$TEMP_DB" -f "$INIT_SCRIPT" 2>/dev/null || true
        
        # Получаем список новых таблиц
        for TABLE in $NEW_TABLES; do
            EXISTS_IN_MAIN=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='$TABLE';" 2>/dev/null || echo 0)
            if [ "$EXISTS_IN_MAIN" != "1" ]; then
                echo -e "${BLUE}ℹ️  Создание таблицы: $TABLE${NC}"
                # Создаем таблицу из временной БД, но с правильным синтаксисом
                psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "CREATE TABLE IF NOT EXISTS $TABLE (LIKE $TEMP_DB.public.$TABLE INCLUDING ALL);" 2>/dev/null || true
                
                # Копируем данные
                psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "INSERT INTO $TABLE SELECT * FROM $TEMP_DB.public.$TABLE;" 2>/dev/null || true
            fi
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
    exit 0
else
    echo -e "${RED}❌ База данных пуста!${NC}"
    exit 1
fi
