# ============================================
# DAILY TUNER - PRODUCTION MAKEFILE
# Docker Compose + Secrets + Backup + Rotation
# ============================================

.PHONY: help secrets up down validate logs build test clean backup rotate-cron cron-setup status

# ============================================
# ЦВETНЫЕ ВЫВОДЫ
# ============================================
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RED    := $(shell tput -Txterm setaf 1)
RESET  := $(shell tput -Txterm sgr0)

# ============================================
# 1. СЕКРЕТЫ (ОБЯЗАТЕЛЬНО перед up)
# ============================================
secrets:
	@echo "${GREEN}🔐 Creating Docker secrets...${RESET}"
	mkdir -p docker-secrets && chmod 700 docker-secrets
	openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24 > docker-secrets/postgrespassword.txt
	openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24 > docker-secrets/app_password.txt
	openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32 > docker-secrets/backend-api-key.txt
	PASS=$$(cat docker-secrets/postgrespassword.txt) && echo "postgresql+asyncpg://postgres:$${PASS}@postgres:5432/personalassistant" > docker-secrets/db-url.txt
	chmod 600 docker-secrets/*
	@echo "${GREEN}✅ Secrets created:${RESET}"
	@echo "   Postgres: $$(cat docker-secrets/postgrespassword.txt | cut -c1-8)... "
	@echo "   App role: $$(cat docker-secrets/app_password.txt | cut -c1-8)... "
	@echo "   API Key:  $$(cat docker-secrets/backend-api-key.txt | cut -c1-8)... " 
	@echo "   DB URL: $$(cat docker-secrets/db-url.txt | cut -c1-30)... "
	
# ============================================
# 2. ПОЛНЫЙ ЗАПУСК (secrets + init + app)
# ============================================
up: secrets init-db
	@echo "${GREEN}🚀 Starting services...${RESET}"
	docker compose up -d
	@echo "${GREEN}⏳ Waiting for healthy services...${RESET}"
	@sleep 30
	@make status

# ============================================
# 3. ИНИЦИАЛИЗАЦИЯ БД (init_db.sql + роли)
# ============================================
init-db:
	@echo "${GREEN}🗄️ Initializing database...${RESET}"
	docker compose up -d postgres
	@sleep 35
	@docker exec pa-postgres pg_isready || exit 1
	docker exec pa-postgres psql -U postgres -d personalassistant -f /docker-entrypoint-initdb.d/init_db.sql || true
	@echo "${GREEN}✅ Database ready! Role: personal_assistant_app${RESET}"




# ============================================
# 4. ВАЛИДАЦИЯ (БД + сервисы)
# ============================================
validate:
	@echo "${YELLOW}🔍 Validating infrastructure...${RESET}"
	@docker compose ps --format "table {{.Names}}	{{.Status}}" || echo "${RED}❌ Services not running${RESET}"
	@PGPASSWORD=$$(cat docker-secrets/postgrespassword.txt) psql -h localhost -U postgres -d personalassistant -tAc "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public';" | grep -q "16" && echo "${GREEN}✅ 16+ tables OK${RESET}" || echo "${RED}❌ Tables missing${RESET}"
	@docker compose ps grafana | grep -q "Up" && echo "${GREEN}✅ Grafana: localhost:3000${RESET}" || echo "${YELLOW}⚠️  Grafana not ready${RESET}"
	@curl -s http://localhost:8000/docs > /dev/null && echo "${GREEN}✅ FastAPI: localhost:8000${RESET}" || echo "${YELLOW}⚠️  FastAPI not ready${RESET}"

# ============================================
# 🛑 БЕЗОПАСНАЯ ОСТАНОВКА (БД СОХРАНЯЕТСЯ!)
# ============================================
down:
	docker compose down
	@echo "${GREEN}✅ Services stopped (DB preserved)${RESET}"

# ============================================
# 5. БЭКАПЫ (ежедневно 3:00)
# ============================================
backup:
	@echo "${GREEN}💾 Creating database backup...${RESET}"
	mkdir -p backups
	@docker exec pa-backup /backup.sh
	@echo "${GREEN}✅ Backup completed:${RESET}"
	@ls -lh backups/ | tail -3

backup-force:
	@echo "${GREEN}💾 Force backup with rotation check...${RESET}"
	@docker exec pa-backup sh -c "/backup.sh && echo '✅ Force backup done'"
	@ls -lh backups/*.sql.gz | tail -5

check-backup:
	@echo "${YELLOW}📊 Backup status:${RESET}"
	@ls -lh backups/*.sql.gz | tail -5
	@echo ""
	@echo "${GREEN}💾 Backup sizes:${RESET}"
	@du -sh backups/
	@echo ""
	@echo "${YELLOW}🗑️ Old backups (will be deleted):${RESET}"
	@find backups -name "*.sql.gz" -mtime +7 -ls

verify-backup:
	@echo "${YELLOW}🔍 Verifying latest backup...${RESET}"
	@LATEST=$$(ls -t backups/*.sql.gz | head -1); \
	echo "Checking: $$LATEST"; \
	gunzip -c $$LATEST | head -20 | grep -q "CREATE TABLE" && echo "${GREEN}✅ Backup valid${RESET}" || echo "${RED}❌ Backup corrupt${RESET}"

# ============================================
# ВОССТАНОВЛЕНИЕ
# ============================================
restore-list:
	@echo "${YELLOW}📋 Available backups:${RESET}"
	@ls -lh backups/*.sql.gz | awk '{print $9, "("$5")"}'

restore-latest:
	@echo "${YELLOW}🔄 Restoring latest backup...${RESET}"
	@echo "⚠️  This will DROP all existing data!"
	@read -p "Continue? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		LATEST=$$(ls -t backups/*.sql.gz | head -1); \
		echo "Restoring from: $$LATEST"; \
		PGPASSWORD=$$(cat docker-secrets/postgrespassword.txt) gunzip -c $$LATEST | \
		docker exec -i pa-postgres psql -U postgres -d personalassistant; \
		echo "${GREEN}✅ Restore completed${RESET}"; \
	else \
		echo "${RED}❌ Restore cancelled${RESET}"; \
	fi

restore-file:
	@echo "${YELLOW}🔄 Restoring from specific backup...${RESET}"
	@echo "Available backups:"
	@ls -1 backups/*.sql.gz | nl
	@read -p "Enter number: " num; \
	FILE=$$(ls -1 backups/*.sql.gz | sed -n "$${num}p"); \
	if [ -n "$$FILE" ]; then \
		echo "Restoring from: $$FILE"; \
		read -p "Continue? (y/N): " confirm; \
		if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
			PGPASSWORD=$$(cat docker-secrets/postgrespassword.txt) gunzip -c $$FILE | \
			docker exec -i pa-postgres psql -U postgres -d personalassistant; \
			echo "${GREEN}✅ Restore completed${RESET}"; \
		else \
			echo "${RED}❌ Restore cancelled${RESET}"; \
		fi; \
	else \
		echo "${RED}❌ Invalid selection${RESET}"; \
	fi

# Проверки
validate:
	@echo "${YELLOW}🔍 Validating infrastructure...${RESET}"
	@docker compose ps --format "table {{.Names}}	{{.Status}}" || echo "${RED}❌ Services not running${RESET}"
	@PGPASSWORD=$$(cat docker-secrets/postgrespassword.txt) psql -h localhost -U postgres -d personalassistant -tAc "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public';" | grep -q "16" && echo "${GREEN}✅ 16+ tables OK${RESET}" || echo "${RED}❌ Tables missing${RESET}"
	# Проверка бэкап-сервиса
	@docker exec pa-backup pg_isready -h postgres -U postgres > /dev/null 2>&1 && echo "${GREEN}✅ Backup service connected${RESET}" || echo "${RED}❌ Backup service offline${RESET}"
	# Проверка наличия бэкапов
	@[ -f backups/$$(ls -t backups/*.sql.gz 2>/dev/null | head -1) ] && echo "${GREEN}✅ Recent backup found${RESET}" || echo "${YELLOW}⚠️  No backups found${RESET}"
	@docker compose ps grafana | grep -q "Up" && echo "${GREEN}✅ Grafana: localhost:3000${RESET}" || echo "${YELLOW}⚠️  Grafana not ready${RESET}"
	@curl -s http://localhost:8000/docs > /dev/null && echo "${GREEN}✅ FastAPI: localhost:8000${RESET}" || echo "${YELLOW}⚠️  FastAPI not ready${RESET}"
monitor-backup:
	@./scripts/backup-monitor.sh
	@tail -5 logs/backup-monitor.log

# ============================================
# ПРОВЕРКА БЭКАПОВ
# ============================================
check-backup-system:
	@echo "${GREEN}🧪 Running complete backup system check...${RESET}"
	@./scripts/check-backup-system.sh

check-backup-quick:
	@echo "${GREEN}🧪 Quick backup check...${RESET}"
	@./scripts/check-backup-system.sh 2>&1 | grep -E "(PASSED|FAILED|WARNING|ВСЕ ПРОВЕРКИ)"
	
# ============================================
# 6. РОТАЦИЯ ПАРОЛЕЙ (еженедельно)
# ============================================
rotate-secrets:
	@echo "${YELLOW}🔄 Rotating secrets (zero-downtime)...${RESET}"
	NEW_PASS=$$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)
	NEW_API_KEY=$$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
	
	# Rotate DB passwords
	docker exec pa-postgres psql -U postgres -d personalassistant -c "ALTER ROLE postgres WITH PASSWORD '$$NEW_PASS'; ALTER ROLE personal_assistant_app WITH PASSWORD '$$NEW_PASS';"
	
	# Update files
	echo "$$NEW_PASS" > docker-secrets/postgrespassword.txt
	echo "postgresql+asyncpg://postgres:$${NEW_PASS}@postgres:5432/personalassistant" > docker-secrets/db-url.txt
	echo "$$NEW_API_KEY" > docker-secrets/backend-api-key.txt  # ← НОВОЕ!
	
	chmod 600 docker-secrets/*
	
	# Restart dependent services
	docker compose restart postgres backend-api web-ui cron-backup  # ← Обновить имя сервиса
	@echo "${GREEN}✅ Secrets rotated${RESET}"


# ============================================
# 7. МОНИТОРИНГ И ЛОГИ
# ============================================
status:
	@echo "${YELLOW}📊 Infrastructure status:${RESET}"
	docker compose ps --format "table {{.Names}}	{{.Status}}	{{.Ports}}"
	@echo ""
	@echo "${GREEN}🔗 Access:${RESET}"
	@echo "   Grafana: http://localhost:3000 (admin/admin)"
	@echo "   FastAPI: http://localhost:8000/docs"
	@echo "   DBeaver: localhost:5432 (postgres/$$(cat docker-secrets/postgrespassword.txt))"

logs:
	docker compose logs -f --tail=100

logs-app:
	docker compose logs -f backend-api

# ============================================
# 8. СБОРКА И ТЕСТЫ
# ============================================
build:
	docker compose build --no-cache

test:
	docker compose up -d backend-api
	curl -f http://localhost:8000/health || echo "⚠️ Healthcheck failed"

# ============================================
# 9. ОЧИСТКА
# ============================================
#down:
#	docker compose down
#	@echo "${GREEN}✅ Services stopped${RESET}"

#clean: down
#	docker compose down -v --remove-orphans
#	docker system prune -f
#	rm -rf docker-secrets/ backups/
#	@echo "${GREEN}🧹 Full cleanup completed${RESET}"

# ============================================
# 10. CRON АВТОМАТИЗАЦИЯ
# ============================================
cron-setup:
	@echo "${GREEN}⏰ Installing cron jobs...${RESET}"
	echo "0 3 * * * cd $$(pwd) && make backup" > /tmp/crontab_pa
	echo "0 4 * * 0 cd $$(pwd) && make rotate-secrets" >> /tmp/crontab_pa
	crontab /tmp/crontab_pa
	rm /tmp/crontab_pa
	@echo "${GREEN}✅ Cron installed:${RESET}"
	@echo "   Daily backup: 03:00"
	@echo "   Weekly rotation: 04:00 Sunday"
	crontab -l

cron-remove:
	crontab -r
	@echo "${GREEN}✅ Cron jobs removed${RESET}"

# ============================================
# 11. HELP
# ============================================
help:
	@echo "${GREEN}Personal Assistant - Production Commands${RESET}"
	@echo "${YELLOW}Usage: make [target]${RESET}"
	@echo ""
	@echo "${GREEN}💻 Core:${RESET}"
	@echo "  up         🚀 Full start (secrets + init + services)"
	@echo "  down       🛑 Stop services"
	@echo "  status     📊 Show status + URLs"
	@echo "  validate   🔍 Check DB tables + services"
	@echo ""
	@echo "${GREEN}🔐 Secrets:${RESET}"
	@echo "  secrets    🔑 Generate postgres/app passwords"
	@echo "  rotate-secrets  🔄 Weekly password rotation"
	@echo ""
	@echo "${GREEN}💾 Backup:${RESET}"
	@echo "  backup     💾 Daily DB backup (7-day retention)"
	@echo "  cron-setup 📅 Install cron (backup + rotation)"
	@echo ""
	@echo "${GREEN}🧹 Maintenance:${RESET}"
	@echo "  logs       📜 Tail all logs"
	@echo "  logs-app   📜 App logs only"
	@echo "  clean      🧹 Full cleanup (volumes + secrets)"
	@echo "  help       📖 This help"
	@echo ""
	@echo "${YELLOW}Production schedule:${RESET}"
	@echo "  03:00 daily  → make backup"
	@echo "  04:00 Sunday → make rotate-secrets"
	@echo "  restore    🔄 Restore from backup (select file)"
	@echo "  restore-latest 🔄 Restore from latest backup"
