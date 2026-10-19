@echo off
set PGPASSWORD=postgres
set TIMESTAMP=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set BACKUP_FILE=backup_grand_crm_%TIMESTAMP%.sql

echo [INFO] PostgreSQL zaxira nusxasi yaratilmoqda: %BACKUP_FILE%
"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -h localhost -p 5432 -U postgres -d grand_crm_db -F p -f "%BACKUP_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo [MUVAFFAQIYATLI] Zaxira nusxasi saqlandi: %BACKUP_FILE%
) else (
    echo [XATOLIK] Zaxira nusxasini olishda xatolik yuz berdi!
)
