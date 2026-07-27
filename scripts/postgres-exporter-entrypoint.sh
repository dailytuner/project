#!/bin/sh
set -e

if [ -f /run/secrets/postgrespassword ]; then
    PASSWORD=$(cat /run/secrets/postgrespassword | tr -d '\n\r')
    export DATA_SOURCE_NAME="postgresql://postgres:${PASSWORD}@postgres:5432/personalassistant?sslmode=disable"
    echo "✅ Password loaded from secret (length: ${#PASSWORD})"
else
    echo "❌ Secret file /run/secrets/postgrespassword not found!"
    exit 1
fi

exec /bin/postgres_exporter "$@"
