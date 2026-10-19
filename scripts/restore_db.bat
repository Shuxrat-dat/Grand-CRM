@echo off
if "%~1"=="" (
    echo [XATOLIK] Iltimos, tiklash uchun SQL fayl nomini ko'rsating!
    echo Misol: scripts\restore_db.bat backup_grand_crm_20261019.sql
    exit /b 1
)

set PGPASSWORD=postgres
set SQL_FILE=%~1

echo [INFO] Ma'lumotlar bazasi qayta tiklanmoqda: %SQL_FILE%
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -h localhost -p 5432 -U postgres -d grand_crm_db -f "%SQL_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo [MUVAFFAQIYATLI] Baza muvaffaqiyatli tiklandi!
) else (
    echo [XATOLIK] Bazani tiklashda xatolik yuz berdi!
)
