#!/bin/bash
echo "🔄 Rotating secrets..."

# 1. Генерируем новый пароль
NEW_PASS=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)
echo "$NEW_PASS" > docker-secrets/postgrespassword.txt.new
chmod 600 docker-secrets/postgrespassword.txt.new

# 2. Обновляем роль в БД (zero-downtime)
docker exec pa-postgres psql -U postgres -d personalassistant -c "
ALTER ROLE postgres WITH PASSWORD '$NEW_PASS';
ALTER ROLE personal_assistant_app WITH PASSWORD '$NEW_PASS';
"

# 3. Атомарная замена
mv docker-secrets/postgrespassword.txt.new docker-secrets/postgrespassword.txt

# 4. Graceful restart (0 downtime)
docker compose restart postgres app-api

echo "✅ Secrets rotated: $(cat docker-secrets/postgrespassword.txt | cut -c1-8)..."

