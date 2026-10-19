#!/usr/bin/env bash
set -e

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="backup_grand_crm_${TIMESTAMP}.sql"

export PGPASSWORD=${DB_PASSWORD:-postgres}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}
DB_NAME=${DB_NAME:-grand_crm_db}

echo "[INFO] PostgreSQL zaxira nusxasi olinmoqda: ${BACKUP_FILE}"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F p -f "$BACKUP_FILE"
echo "[MUVAFFAQIYATLI] Zaxira nusxasi tayyor: ${BACKUP_FILE}"
