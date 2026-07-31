```markdown
# 📊 MONITORING — PostgreSQL + Prometheus + Grafana

Полноценный мониторинг PostgreSQL, системных метрик VPS и состояния приложения.

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         VPS                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  PostgreSQL  │────▶│  postgres-   │────▶│  Prometheus  │   │
│  │              │     │  exporter    │     │   (Storage)  │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  БД          │     │  Метрики     │     │   Grafana    │   │
│  │  (Port 5432) │     │  (Port 9187) │     │  (Port 3001) │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ SSH Tunnel
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DESKTOP (Ваш ПК)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Browser                              │  │
│  │              http://localhost:3001                      │  │
│  │              (SSH Tunnel → VPS:3001)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Быстрый запуск

```bash
# 1. Запустить мониторинг
docker compose up -d prometheus postgres-exporter grafana

# 2. Проверить статус
docker compose ps

# 3. Подключиться к Grafana (на десктопе)
ssh -i ~/.ssh/dt -L 3001:localhost:3001 -L 9090:localhost:9090 -L 9187:localhost:9187 root@80.93.63.17

# 4. Открыть браузер
# http://localhost:3001  — Grafana
# http://localhost:9090  — Prometheus UI
# http://localhost:9187/metrics — Метрики exporter
```

---

## 🔧 Команды управления

### Запуск/остановка

```bash
# Запустить мониторинг
docker compose up -d prometheus postgres-exporter grafana

# Остановить мониторинг
docker compose stop prometheus postgres-exporter grafana

# Перезапустить
docker compose restart prometheus postgres-exporter grafana

# Статус
docker compose ps
```

### Логи

```bash
# Логи postgres-exporter
docker logs pa-postgres-exporter --tail 50

# Логи Prometheus
docker logs pa-prometheus --tail 50

# Логи Grafana
docker logs pa-grafana --tail 50

# Все логи мониторинга
docker compose logs -f prometheus postgres-exporter grafana
```

### Проверка

```bash
# Проверка postgres-exporter
curl -s http://localhost:9187/metrics | grep pg_up

# Проверка Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=pg_up' | python3 -m json.tool

# Проверка Grafana
curl -s http://localhost:3001/api/health

# Проверка подключения к БД
docker exec pa-postgres psql -U postgres -d personalassistant -c "SELECT 1"
```

---

## 🔐 Пароли и секреты

### Основные пароли

| Сервис | Где хранится | Как посмотреть |
|--------|--------------|----------------|
| **PostgreSQL** | `docker-secrets/postgrespassword.txt` | `cat docker-secrets/postgrespassword.txt` |
| **Grafana** | `docker-secrets/grafana-password.txt` | `cat docker-secrets/grafana-password.txt` |

### Права на секреты

```bash
# Секреты должны быть доступны для чтения
chmod 644 docker-secrets/postgrespassword.txt
chmod 600 docker-secrets/grafana-password.txt
```

### Ротация паролей PostgreSQL

```bash
# Ручная ротация
./scripts/rotate-postgres-password.sh

# Автоматическая (еженедельно) — добавить в crontab:
0 4 * * 0 cd /root/project && ./scripts/rotate-postgres-password.sh >> /var/log/password-rotation.log 2>&1
```

---

## 📊 Grafana

### Доступ

```bash
# 1. Открыть SSH туннель (на десктопе)
ssh -i ~/.ssh/dt -L 3001:localhost:3001 root@"IP"

# 2. В браузере
http://localhost:3001

# 3. Вход
Логин: admin
Пароль: cat docker-secrets/grafana-password.txt
```

### Data Source

| Поле | Значение |
|------|----------|
| **Name** | `Prometheus` |
| **Type** | `Prometheus` |
| **URL** | `http://prometheus:9090` |
| **Access** | `Server (default)` |

### Дашборды

| Дашборд | ID | Описание |
|---------|-----|----------|
| **PostgreSQL** | `9628` | Полный мониторинг БД |
| **Node Exporter** | `1860` | Системные метрики VPS |

**Импорт:** Dashboards → Import → Ввести ID → Load → Select Prometheus → Import

---

## 📈 Проверка метрик

### postgres-exporter (порт 9187)

```bash
# Все метрики
curl -s http://localhost:9187/metrics

# Проверить, что БД жива
curl -s http://localhost:9187/metrics | grep pg_up
# Должно быть: pg_up 1

# Количество подключений
curl -s http://localhost:9187/metrics | grep pg_stat_database_numbackends

# Cache hit ratio
curl -s http://localhost:9187/metrics | grep pg_stat_database_blks_hit
```

### Prometheus (порт 9090)

```bash
# Проверить статус
curl -s http://localhost:9090/-/healthy

# Метрики через API
curl -s 'http://localhost:9090/api/v1/query?query=pg_up' | python3 -m json.tool

# Список целей (targets)
curl -s 'http://localhost:9090/api/v1/targets' | python3 -m json.tool
```

---

## 🛠️ Конфигурационные файлы

### Структура

```
project/
├── config/
│   ├── prometheus/
│   │   └── prometheus.yml          # Конфиг Prometheus
│   └── grafana/
│       ├── datasources/
│       │   └── prometheus.yml      # Datasource для Grafana
│       └── dashboards/              # Дашборды (опционально)
├── scripts/
│   ├── postgres-exporter-entrypoint.sh
│   └── rotate-postgres-password.sh
├── docker-secrets/
│   ├── postgrespassword.txt
│   └── grafana-password.txt
└── docker-compose.yml
```

## 🐛 Устранение неполадок

### 1. postgres-exporter не может подключиться к БД

**Симптом:** В логах `password authentication failed`

**Решение:**
```bash
# 1. Проверить пароль
cat docker-secrets/postgrespassword.txt

# 2. Проверить, что пароль работает
PGPASSWORD=$(cat docker-secrets/postgrespassword.txt) \
docker exec pa-postgres psql -U postgres -d personalassistant -c "SELECT 1"

# 3. Сбросить пароль
docker exec pa-postgres psql -U postgres -d postgres -c \
  "ALTER USER postgres WITH PASSWORD '$(cat docker-secrets/postgrespassword.txt)';"

# 4. Перезапустить
docker compose restart postgres-exporter
```

### 2. postgres-exporter не может прочитать секрет

**Симптом:** `Permission denied` при чтении `/run/secrets/postgrespassword`

**Решение:**
```bash
# Дать права на чтение секрета
chmod 644 docker-secrets/postgrespassword.txt

# Перезапустить
docker compose restart postgres-exporter
```

### 3. Prometheus не видит postgres-exporter

**Симптом:** В `http://localhost:9090/targets` статус `DOWN`

**Решение:**
```bash
# 1. Проверить, что exporter работает
curl -s http://localhost:9187/metrics

# 2. Проверить конфиг Prometheus
cat config/prometheus/prometheus.yml

# 3. Перезапустить Prometheus
docker compose restart prometheus
```

### 4. Не подключается к Grafana

**Симптом:** `http://localhost:3001` не открывается

**Решение:**
```bash
# 1. Проверить, что Grafana работает
docker ps | grep grafana

# 2. Проверить порт
curl -s http://localhost:3001/api/health

# 3. Открыть туннель (на десктопе)
ssh -i ~/.ssh/dt -L 3001:localhost:3001 root@80.93.63.17
```

### 5. В Grafana не отображаются метрики

**Симптом:** В дашборде нет данных

**Решение:**
```bash
# 1. Проверить, что метрики есть
curl -s http://localhost:9187/metrics | grep pg_up

# 2. Проверить datasource в Grafana
# Settings → Data Sources → Prometheus → URL: http://prometheus:9090

# 3. Проверить в Explorer
# Explore → Prometheus → Запрос: pg_up
```

---

## 📋 Ресурсы

| Контейнер | Порт | Память | CPU |
|-----------|------|--------|-----|
| **prometheus** | 9090 | 256MB | 0.2 |
| **postgres-exporter** | 9187 | 64MB | 0.1 |
| **grafana** | 3001 | 256MB | 0.2 |

**Итого:** ~576MB RAM, 0.5 CPU

---

## 💎 Полезные команды

```bash
# Полный статус
docker compose ps

# Перезапустить всё
docker compose restart

# Остановить всё
docker compose down

# Обновить конфиги и перезапустить
docker compose restart prometheus grafana
```

