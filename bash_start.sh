#!/bin/bash
set -e

echo "🚀 Personal Assistant - PRODUCTION READY"

# 1. Secrets
./scripts/set-app-password.sh
POSTGRES_PASS=$(cat docker-secrets/postgrespassword.txt)
APP_PASS=$(cat docker-secrets/app_password.txt)
echo "🔐 Password: $POSTGRES_PASS"

# 2. Postgres + init
make down
docker compose up -d postgres
sleep 25
docker exec pa-postgres psql -U postgres -d personalassistant -f /docker-entrypoint-initdb.d/init_db.sql || true

# 3. Пароли (БЕЗ Makefile ошибок!)
docker exec pa-postgres psql -U postgres -c "ALTER ROLE postgres WITH PASSWORD '$POSTGRES_PASS';"
docker exec pa-postgres psql -U postgres -c "ALTER ROLE personal_assistant_app WITH PASSWORD '$APP_PASS';"

# 4. Full stack
docker compose up -d

# 5. Тест
PGPASSWORD=$POSTGRES_PASS psql -h localhost -U postgres -d personalassistant -c "\dt" | head -5
echo "✅ DATABASE OK! DBeaver: localhost:5432 postgres/$POSTGRES_PASS"
echo "🌐 API: http://localhost:8000"
echo "📊 Grafana: http://localhost:3000"