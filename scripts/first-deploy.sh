#!/bin/bash
# first-deploy.sh

set -e

echo "🚀 Personal Assistant - First Deployment"
echo "========================================="

# 1. Создаем директории
mkdir -p docker-secrets backups logs .docker-cache/{ephemeris,timezone,pip}

# 2. Генерируем секреты
echo "🔐 Generating secrets..."
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24 > docker-secrets/postgrespassword.txt
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32 > docker-secrets/backend-api-key.txt
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24 > docker-secrets/grafana-password.txt

# 3. Создаем db-url
PASS=$(cat docker-secrets/postgrespassword.txt)
echo "postgresql+asyncpg://postgres:${PASS}@postgres:5432/personalassistant" > docker-secrets/db-url.txt

# 4. Проверяем bot-token
if [ ! -f docker-secrets/bot-token.txt ]; then
    echo "⚠️  Please enter your Telegram Bot Token:"
    read -r TOKEN
    echo "$TOKEN" > docker-secrets/bot-token.txt
fi

chmod 600 docker-secrets/*

# 5. Скачиваем кэши (один раз)
echo "📦 Downloading caches (this may take a few minutes)..."
cd .docker-cache/ephemeris
for f in seas_18.se1 semo_18.se1 sepl_18.se1 sefstars.txt; do
    [ -f $f ] || wget -q https://github.com/aloistr/swisseph/raw/master/ephe/$f
done
cd ../timezone
[ -f timezones.geojson.zip ] || wget -q https://github.com/evansiroky/timezone-boundary-builder/releases/download/2023d/timezones.geojson.zip
cd ../..

# 6. Строим и запускаем
echo "🏗️ Building images..."
DOCKER_BUILDKIT=1 docker compose build --parallel

echo "🚀 Starting services..."
docker compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# 7. Проверка
echo "🔍 Validating..."
docker compose ps

echo ""
echo "✅ Deployment complete!"
echo "📊 Access:"
echo "   API: http://localhost:8000/docs"
echo "   Grafana: http://localhost:3001 (admin/$(cat docker-secrets/grafana-password.txt))"
echo "   Postgres: localhost:5432 (postgres/$(cat docker-secrets/postgrespassword.txt | cut -c1-8)...)"
echo ""
echo "📝 Next steps:"
echo "   - Check logs: docker compose logs -f"
echo "   - Stop: docker compose down"
echo "   - Daily backup: add to crontab"
