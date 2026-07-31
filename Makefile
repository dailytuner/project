# ============================================
# DAILY TUNER - PRODUCTION MAKEFILE
# Docker Compose + Secrets + Backup + Rotation
# ============================================

.PHONY: help secrets up down validate logs build test clean backup rotate-cron cron-setup status \
        check-backup verify-backup clean-backups restore-latest restore-list restore-file \
        safe-clean clean-fast db-status db-tables check-all logs-backup logs-backup-error

# ============================================
# ЦВЕТНЫЕ ВЫВОДЫ
# ============================================
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RED    := $(shell tput -Txterm setaf 1)
BLUE   := $(shell tput -Txterm setaf 4)
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
	@TABLE_COUNT=$$(PGPASSWORD=$$(cat docker-secrets/postgrespassword.txt) psql -h localhost -U postgres -d personalassistant -tAc "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public';" 2>/dev/null || echo 0); \
	if [ "$$TABLE_COUNT" -gt 0 ]; then \
		echo "${GREEN}✅ $$TABLE_COUNT tables OK${RESET}"; \
	else \
		echo "${RED}❌ Tables missing${RESET}"; \
	fi
	@docker compose ps grafana 2>/dev/null | grep -q "Up" && echo "${GREEN}✅ Grafana: localhost:3000${RESET}" || echo "${YELLOW}⚠️  Grafana not ready${RESET}"
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
	@docker exec pa-backup /backup.sh || { echo "${RED}❌ Backup failed${RESET}"; exit 1; }
	@echo "${GREEN}✅ Backup completed:${RESET}"
	@ls -lh backups/ | grep ".sql.gz" | tail -3

# ============================================
# 6. ПРОВЕРКА БЭКАПОВ
# ============================================
check-backup:
	@echo "${YELLOW}📊 Backup status:${RESET}"
	@echo ""
	@echo "Latest 3 backups:"
	@ls -lh backups/*.sql.gz 2>/dev/null | tail -3 || echo "No backups found"
	@echo ""
	@echo "Total size:"
	@du -sh backups/ 2>/dev/null || echo "0"
	@echo ""
	@echo "Old backups (>7 days):"
	@find backups -name "*.sql.gz" -mtime +7 -ls 2>/dev/null || echo "None"

verify-backup:
	@echo "${YELLOW}🔍 Verifying latest backup...${RESET}"
	@LATEST=$$(ls -t backups/*.sql.gz 2>/dev/null | head -1); \
	if [ -n "$$LATEST" ]; then \
		echo "Checking: $$LATEST"; \
		if gunzip -c $$LATEST 2>/dev/null | head -50 | grep -q "CREATE TABLE"; then \
			echo "${GREEN}✅ Backup is valid (contains CREATE TABLE)${RESET}"; \
			COUNT=$$(gunzip -c $$LATEST 2>/dev/null | grep -c "CREATE TABLE" || echo 0); \
			echo "Found $$COUNT tables in backup"; \
		else \
			echo "${RED}❌ Backup appears invalid${RESET}"; \
		fi; \
	else \
		echo "${RED}❌ No backups found${RESET}"; \
	fi

clean-backups:
	@echo "${YELLOW}🧹 Cleaning old backups...${RESET}"
	@echo "Current backups:"
	@ls -lh backups/*.sql.gz 2>/dev/null || echo "No backups"
	@echo ""
	@read -p "Delete backups older than 7 days? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		find backups -name "*.sql.gz" -mtime +7 -delete; \
		echo "${GREEN}✅ Old backups deleted${RESET}"; \
	else \
		echo "${RED}❌ Cleanup cancelled${RESET}"; \
	fi

# ============================================
# 7. ВОССТАНОВЛЕНИЕ
# ============================================
restore-list:
	@echo "${YELLOW}📋 Available backups:${RESET}"
	@ls -lh backups/*.sql.gz 2>/dev/null | awk '{print NR, $$9, "("$$5")"}' || echo "No backups found"

restore-latest:
	@echo "${YELLOW}🔄 Restoring latest backup...${RESET}"
	@LATEST=$$(ls -t backups/*.sql.gz 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "${RED}❌ No backups found${RESET}"; \
		exit 1; \
	fi; \
	echo "⚠️  This will DROP all existing data!"; \
	read -p "Continue? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
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
	@ls -1 backups/*.sql.gz 2>/dev/null | nl || { echo "${RED}❌ No backups found${RESET}"; exit 1; }
	@read -p "Enter number: " num; \
	FILE=$$(ls -1 backups/*.sql.gz 2>/dev/null | sed -n "$${num}p"); \
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

# ============================================
# 8. РОТАЦИЯ ПАРОЛЕЙ (еженедельно)
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
	echo "$$NEW_API_KEY" > docker-secrets/backend-api-key.txt
	
	chmod 600 docker-secrets/*
	
	# Restart dependent services
	docker compose restart postgres backend-api web-ui cron-backup
	@echo "${GREEN}✅ Secrets rotated${RESET}"

# ============================================
# 9. МОНИТОРИНГ И ЛОГИ
# ============================================
status:
	@echo "${YELLOW}📊 Infrastructure status:${RESET}"
	docker compose ps --format "table {{.Names}}	{{.Status}}	{{.Ports}}"
	@echo ""
	@echo "${GREEN}🔗 Access:${RESET}"
	@echo "   FastAPI: http://localhost:8000/docs"
	@echo "   Web UI: http://localhost:8080"
	@echo "   DBeaver: localhost:5432 (postgres/$$(cat docker-secrets/postgrespassword.txt))"

logs:
	docker compose logs -f --tail=100

logs-app:
	docker compose logs -f backend-api

logs-backup:
	@echo "${GREEN}📋 Backup logs:${RESET}"
	@docker exec pa-backup tail -20 /logs/backup.log 2>/dev/null || echo "No logs yet"

logs-backup-error:
	@echo "${RED}📋 Backup error logs:${RESET}"
	@docker exec pa-backup tail -20 /logs/backup_error.log 2>/dev/null || echo "No errors"

logs-restore:
	docker compose logs db-restore

# ============================================
# 10. СБОРКА И ТЕСТЫ
# ============================================
build:
	docker compose build --no-cache

test:
	docker compose up -d backend-api
	curl -f http://localhost:8000/health || echo "⚠️ Healthcheck failed"

# ============================================
# 11. БАЗА ДАННЫХ
# ============================================
db-status:
	@echo "${GREEN}📊 Database status:${RESET}"
	@echo "Tables:"
	@docker exec pa-postgres psql -U postgres -d personalassistant -c "\dt" | tail -n +4 | head -n -2 | wc -l | xargs echo "  Total:"
	@echo ""
	@echo "Users:"
	@docker exec pa-postgres psql -U postgres -d personalassistant -c "SELECT COUNT(*) as count FROM users;"
	@echo ""
	@echo "Backups:"
	@ls -lh backups/*.sql.gz 2>/dev/null | tail -3 || echo "  No backups"

db-tables:
	@echo "${GREEN}📋 All tables:${RESET}"
	@docker exec pa-postgres psql -U postgres -d personalassistant -c "\dt"

# ============================================
# 12. ОЧИСТКА
# ============================================
clean:
	@echo "${RED}⚠️  This will remove all containers, volumes, and data!${RESET}"
	@read -p "Continue? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker compose down -v --remove-orphans; \
		docker system prune -f; \
		rm -rf docker-secrets/ backups/ logs/; \
		echo "${GREEN}🧹 Full cleanup completed${RESET}"; \
	else \
		echo "${RED}❌ Cancelled${RESET}"; \
	fi

# ============================================
# 13. БЕЗОПАСНАЯ ОЧИСТКА
# ============================================
safe-clean:
	@echo "${GREEN}🧹 Running safe cleanup...${RESET}"
	@./scripts/safe-cleanup.sh || { echo "${RED}❌ Safe cleanup failed${RESET}"; exit 1; }

clean-fast:
	@echo "${YELLOW}⚠️  Fast cleanup (without backup check)${RESET}"
	@read -p "Continue? (y/N): " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		docker compose down -v --remove-orphans; \
		echo "${GREEN}✅ Cleanup completed${RESET}"; \
	else \
		echo "${RED}❌ Cancelled${RESET}"; \
	fi

# ============================================
# 14. CRON АВТОМАТИЗАЦИЯ
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
# 15. ПОЛНАЯ ПРОВЕРКА
# ============================================
check-all:
	@echo "${GREEN}🔍 Running full system check...${RESET}"
	@./scripts/check-all.sh || { echo "${RED}❌ Check failed${RESET}"; exit 1; }

check-quick:
	@echo "${GREEN}⚡ Quick check...${RESET}"
	@echo "Status:"
	@docker compose ps --format "table {{.Names}}\t{{.Status}}"
	@echo ""
	@echo "Latest backup:"
	@ls -lh backups/*.sql.gz 2>/dev/null | tail -1 || echo "No backups"
	@echo ""
	@echo "DB status:"
	@make db-status

# ============================================
# 16. HELP
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
	@echo "  check-backup  📊 Check backup status"
	@echo "  verify-backup 🔍 Verify backup integrity"
	@echo "  clean-backups 🧹 Clean old backups (>7 days)"
	@echo "  cron-setup 📅 Install cron (backup + rotation)"
	@echo ""
	@echo "${GREEN}🔄 Restore:${RESET}"
	@echo "  restore-latest  🔄 Restore latest backup"
	@echo "  restore-list    📋 List all backups"
	@echo "  restore-file    🔄 Restore specific backup"
	@echo ""
	@echo "${GREEN}🗄️ Database:${RESET}"
	@echo "  db-status  📊 Show database status"
	@echo "  db-tables  📋 Show all tables"
	@echo ""
	@echo "${GREEN}📋 Logs:${RESET}"
	@echo "  logs       📜 Tail all logs"
	@echo "  logs-app   📜 App logs only"
	@echo "  logs-backup 📜 Backup logs only"
	@echo "  logs-backup-error 📜 Backup error logs"
	@echo "  logs-restore 📜 Restore logs"
	@echo ""
	@echo "${GREEN}🧹 Maintenance:${RESET}"
	@echo "  clean      🧹 Full cleanup (volumes + secrets)"
	@echo "  safe-clean 🧹 Safe cleanup with backup check"
	@echo "  clean-fast 🧹 Fast cleanup without backup"
	@echo ""
	@echo "${GREEN}🔍 Checks:${RESET}"
	@echo "  check-all  🔍 Full system check"
	@echo "  check-quick ⚡ Quick status check"
	@echo "  help       📖 This help"
	@echo ""
	@echo "${YELLOW}Production schedule:${RESET}"
	@echo "  03:00 daily  → make backup"
	@echo "  04:00 Sunday → make rotate-secrets"
