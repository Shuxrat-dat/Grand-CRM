# Grand CRM — O‘quv markazini boshqarish tizimi

Production-darajasidagi to‘liq funksional CRM-tizim. Tizim o‘quv markazining ma'muriy, akademik va moliyaviy jarayonlarini to‘liq avtomatlashtirish, qat'iy buxgalteriya hisobini yuritish va xatoliklarning oldini olish uchun ishlab chiqilgan.

---

## 1. Texnologik stek

- **Backend:** Python 3.12+, Django 6.1+
- **Ma'lumotlar bazasi:** PostgreSQL 17 (psycopg3 orqali tranzaksiyalar va qator darajasidagi blokirovkalar bilan)
- **Frontend / UI:** Django Templates, Bootstrap 5, Bootstrap Icons, HTMX
- **Analitika va grafiklar:** Chart.js
- **Eksport:** `openpyxl` (Excel), `reportlab` (PDF)
- **Testlash:** Django TestCase / Pytest
- **Konteynerlashtirish:** Docker, Docker Compose
- **Til va Valyuta:** O‘zbek tili (Lotin alifbosi), UZS (so'm), Asia/Tashkent vaqt zonasi

---

## 2. Asosiy modullar va imkoniyatlar

### A. Boshqaruv paneli (Dashboard)
- **Ega (Owner) uchun:** Haqiqiy ma'lumotlar bazasidan hisoblanadigan ko'rsatkichlar: faol o'quvchilar, guruhlar, o'qituvchilar, oylik hisoblangan summalar (Accrual), haqiqiy kassa tushumlari (Cash Inflows), o'quvchilar qarzdorligi, o'qituvchilar maoshi, operatsion xarajatlar, hisoblangan operatsion foyda, oxirgi 6 oylik kassa dinamikasi grafigi va yaqinlashayotgan to'lov muddatlari.
- **Administrator uchun:** Bugungi darslar ro'yxati, davomati kutilayotgan guruhlar, to'lov kiritish tezkor tugmalari va to'lov eslatmasi yuborilishi kerak bo'lgan qarzdorlar ro'yxati. Administrator moliyaviy foyda, xarajatlar va ish haqi summalarini ko'rmaydi.

### B. O‘quvchilar (Students)
- F.I.SH., telefon raqamlari, ota-onasi raqami, tug'ilgan sana, kelgan sana, holati (`faol`, `muzlatilgan`, `bitirgan`, `arxivlangan`).
- To'liq profil: a'zo bo'lgan guruhlar, to'lovlar tarixi, hisoblar balansi, qarzdorlik va oldindan to'langan depozit summasi.
- Arxivlash imkoniyati (o'quvchi arxivga o'tkazilganda uning barcha tarixiy to'lovlari, darslari va qarzlari to'liq saqlanadi).

### C. Kurslar va Guruhlar (Academics)
- **Kurslar:** Standart oylik narx va davomiylik. Kurs narxining o'zgarishi mavjud guruhlar va tarixiy hisoblarga ta'sir qilmaydi.
- **O'qituvchilar:** F.I.SH., telefon, mutaxassislik. Har bir o'qituvchi uchun amal qilish boshlanishi va tugashi ko'rsatilgan qat'iy oylik stavka tarixi (`TeacherSalaryRate`). Kelgusidagi stavkaning o'zgarishi o'tgan oylarga ta'sir ko'rsatmaydi.
- **Guruhlar va dars jadvali:** Guruh sig'imi, xonalar va dars vaqtlari. Jadval qo'shishda o'qituvchi va xonaning dars vaqti to'qnashuvini (overlap) avtomatik aniqlash.
- **A'zolik va Ko'chirish:** Guruhga qabul qilishda oylik narx snapshot sifatida yozib olinadi. O'quvchini boshqa guruhga ko'chirishda (`Transfer`) eski a'zolik tarixi to'liq arxivlanadi.

### D. Davomat (Attendance)
- Rejalashtirilgan darslar bo'yicha elektron davomat jurnali: `Qatnashdi`, `Qatnashmadi`, `Kechikdi`, `Sababli`.
- Faqat guruhga dars sanasida amalda a'zo bo'lgan o'quvchilar ko'rinadi.
- Takroriy davomat belgilanishiga qarshi UniqueConstraint himoyasi.
- Belgilangan davomat o'zgartirilganda kim, qachon va qanday o'zgartirgani `AuditLog` jurnalida saqlanadi.

### E. Oylik hisoblar va To‘lovlar (Billing & Payments)
- **Hisoblangan summa (Accrual) vs Kassa tushumi (Cash):** Xizmat uchun oylik hisob (`MonthlyCharge`) va haqiqatda to'langan pul (`Payment`) qat'iy ajratilgan.
- **To'liq bo'lmagan oy siyosati (Proration):** 
  1. `To'liq oylik to'lov (Full month)`
  2. `Kunlarga proporsional (Proportional)` — oy o'rtasida kelgan o'quvchiga faqat amaldagi kunlar hisoblanadi.
- **To'lov taqsimoti (FIFO Allocation):** Yangi to'lov qabul qilinganda avtomatik ravishda eng eski qarzlar yopiladi.
- **Oldindan to'lov (Depozit):** Hisoblangan qarzdan ortiqcha to'langan pul o'quvchi depozitida saqlanadi va kelgusi oy hisobiga avtomatik yo'naltiriladi.
- **Idempotentlik:** Tarmoqdagi takroriy so'rovlar tufayli to'lov ikki marta yechilishining oldini oluvchi `idempotency_key` himoyasi.
- **Storno (Bekor qilish):** To'lov yoki hisob bekor qilinganda yozuv jismonan o'chirilmaydi, storno holatiga o'tkaziladi va sababi bilan auditga yoziladi.

### F. O‘qituvchilar ish haqi (Payroll — Faqat Ega uchun)
- O'qituvchining joriy qat'iy stavkasi bo'yicha maosh hisoblash (`SalaryRecord`).
- Ega tomonidan tasdiqlash (`Approve`) va to'lov berish (`SalaryPayment`).
- Ruxsatsiz ortiqcha to'lov berishdan himoyalangan qoldiq nazorati.

### G. Operatsion xarajatlar (Expenses — Faqat Ega uchun)
- Ijara, kommunal xizmatlar, marketing, soliqlar, kantselyariya va boshqa xarajatlar hisobi.
- Bekor qilish sabablari saqlanadi.

### H. Hisobotlar va Eksport (Reporting)
- Pul oqimi (Cash Flow) hisoboti
- Hisoblangan operatsion foyda (Accrual P&L) hisoboti
- To'lovlar va qarzdorlar hisoboti
- Guruhlar daromadi tahlili
- Davomat statistikasi
- Barcha hisobotlarni Excel (`.xlsx`) va PDF formatlarida bir klik bilan yuklab olish

---

## 3. O‘rnatish va mahalliy ishga tushirish (Local Setup)

### 1-qadam. Virtual muhitni faollashtirish va kutubxonalarni o'rnatish
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2-qadam. Muhit parametrlarini sozlash (.env)
Loyihada `.env` faylini tekshiring (yoki `.env.example` dan nusxa oling):
```env
DEBUG=True
SECRET_KEY=grand-crm-secret-key-production-change-2026
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

DB_ENGINE=django.db.backends.postgresql
DB_NAME=grand_crm_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

TIME_ZONE=Asia/Tashkent
LANGUAGE_CODE=uz
```

### 3-qadam. Migratsiyalarni amalga oshirish
```powershell
python manage.py migrate
```

### 4-qadam. Boshlang'ich Ega (Owner) hisobini yaratish
```powershell
python manage.py create_initial_owner
```
*Standart parametrlar:*
- **Login:** `owner`
- **Parol:** `owner123`
- **Roli:** `Ega (Owner)`

*(Ixtiyoriy) Tizimni sinab ko'rish uchun tayyor demo ma'lumotlarni yuklash:*
```powershell
python manage.py populate_demo_data
```
Bu buyruq tayyor kurslar, o'qituvchilar, guruhlar, o'quvchilar va qo'shimcha `admin` / `admin123` hisobini yaratadi.

### 5-qadam. Serverni ishga tushirish
```powershell
python manage.py runserver
```
Brauzerda oching: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 4. Docker Compose orqali ishga tushirish

Loyiha to'liq Docker muhitida ishlashga moslashtirilgan. PostgreSQL va Django bir buyruq bilan ishga tushadi:

```bash
docker compose up --build -d
```
Tizim avtomatik ravishda migratsiyalarni bajaradi va dastlabki egasini yaratadi.
Sayt: [http://localhost:8000](http://localhost:8000)

---

## 5. Avtomatlashtirilgan testlarni ishga tushirish

Barcha 18 ta biznes-ssenariy to'liq sinovdan o'tkazilgan (20 ta test):
```powershell
python manage.py test tests
```

---

## 6. PostgreSQL zaxira nusxasi va qayta tiklash (Backup & Restore)

### Zaxira nusxa yaratish:
Windows uchun:
```powershell
.\scripts\backup_db.bat
```
Linux / Docker uchun:
```bash
./scripts/backup_db.sh
```

### Zaxira nusxadan qayta tiklash:
Windows uchun:
```powershell
.\scripts\restore_db.bat backup_grand_crm_YYYYMMDD_HHMMSS.sql
```
Linux / Docker uchun:
```bash
./scripts/restore_db.sh backup_grand_crm_YYYYMMDD_HHMMSS.sql
```

---

## 7. Xavfsizlik va Ega tomonidan tasdiqlanishi kerak bo'lgan qarorlar

1. **Production Secret Key:** Production serverga o'rnatishda `.env` faylidagi `SECRET_KEY` va `DEBUG=False` qiymatlarini belgilash lozim.
2. **To'liq bo'lmagan oy siyosati:** Ega sozlamalar bo'limida (`/auth/settings/`) markaz uchun standart hisoblash usulini (`FULL_MONTH` yoki `PROPORTIONAL`) tanlashi mumkin.
3. **Har oylik to'lov muddati:** Standart holatda har oyning 5-sanasi belgilangan. Ega ushbu muddatni o'z markazi qoidalariga mos ravishda o'zgartirishi mumkin.
