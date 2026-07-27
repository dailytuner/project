#!/bin/bash
# ============================================================
# ПРОВЕРКА .pgpass И ПОДКЛЮЧЕНИЯ
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔍 Checking pgpass and connection...${NC}"

# 1. Проверить секрет
if [ -f docker-secrets/postgrespassword.txt ]; then
    PASSWORD=$(cat docker-secrets/postgrespassword.txt)
    echo -e "${GREEN}✅ Secret file exists (length: ${#PASSWORD})${NC}"
else
    echo -e "${RED}❌ Secret file not found!${NC}"
    exit 1
fi

# 2. Проверить .pgpass внутри контейнера
echo -e "${YELLOW}📂 Checking .pgpass inside container...${NC}"
docker exec pa-pgwatch2 ls -la /run/secrets/pgpass 2>/dev/null || {
    echo -e "${RED}❌ .pgpass not found in container!${NC}"
    echo -e "${YELLOW}   Check docker-compose.yml secrets section${NC}"
    exit 1
}

# 3. Проверить подключение через .pgpass
echo -e "${YELLOW}🔗 Testing connection via .pgpass...${NC}"
docker exec pa-pgwatch2 psql -h postgres -U postgres -d personalassistant -c "SELECT 1" > /dev/null 2>&1 && {
    echo -e "${GREEN}✅ Connection successful via .pgpass${NC}"
} || {
    echo -e "${RED}❌ Connection failed!${NC}"
    echo -e "${YELLOW}   Check .pgpass content:${NC}"
    docker exec pa-pgwatch2 cat /run/secrets/pgpass 2>/dev/null || echo "   File not accessible"
    exit 1
}

# 4. Проверить метрики
echo -e "${YELLOW}📊 Checking Prometheus metrics...${NC}"
if curl -s http://localhost:9090/metrics 2>/dev/null | grep -q "pg_up"; then
    echo -e "${GREEN}✅ Metrics are being collected${NC}"
else
    echo -e "${RED}❌ No metrics found!${NC}"
    echo -e "${YELLOW}   Check: docker logs pa-pgwatch2 --tail 20${NC}"
fi

echo -e "${GREEN}✅ All checks passed!${NC}"
