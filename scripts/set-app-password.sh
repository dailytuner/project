#!/bin/bash
echo "🔐 Setting app password..."

# Создать секрет (один файл!)
mkdir -p docker-secrets && chmod 700 docker-secrets
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24 > docker-secrets/postgrespassword.txt
chmod 600 docker-secrets/postgrespassword.txt

# Установить в БД
if docker ps | grep -q pa-postgres; then
  PGPASSWORD=$(cat docker-secrets/postgrespassword.txt) \
  docker exec pa-postgres psql -U postgres -d personalassistant -c "
    ALTER ROLE postgres WITH PASSWORD '$(cat docker-secrets/postgrespassword.txt)';
    ALTER ROLE personal_assistant_app WITH PASSWORD '$(cat docker-secrets/postgrespassword.txt)';
  "
fi

echo "✅ Password: $(cat docker-secrets/postgrespassword.txt)"

