#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
    echo "[XATOLIK] Fayl ko'rsatilmadi! Misol: ./scripts/restore_db.sh backup.sql"
    exit 1
fi

SQL_FILE="$1"
export PGPASSWORD=${DB_PASSWORD:-postgres}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}
DB_NAME=${DB_NAME:-grand_crm_db}

echo "[INFO] Tiklash boshlandi: ${SQL_FILE}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"
echo "[MUVAFFAQIYATLI] Baza muvaffaqiyatli tiklandi!"
