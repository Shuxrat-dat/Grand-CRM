# Bepul bulutga joylashtirish bo‘yicha qo‘llanma (Variant 2)

Ushbu qo‘llanma orqali CRM tizimini **100% bepul** bulutli serverga (Koyeb yoki Render) va bepul PostgreSQL ma'lumotlar bazasiga (Supabase) 5 daqiqada joylashtirishingiz mumkin.

---

## 1-Qadam: Bepul PostgreSQL bazasi yaratish (Supabase)

1. **[Supabase.com](https://supabase.com)** saytiga kiring va bepul ro‘yxatdan o‘ting (GitHub yoki Email orqali).
2. **"New Project"** tugmasini bosing:
   * **Name:** `grand-crm-db`
   * **Database Password:** o‘zingiz eslab qoladigan kuchli parol yozing (masalan: `GrandCRM2026!Db`).
   * **Region:** Frankfurt yoki Singapore (O‘zbekistonga eng yaqin serverlar).
3. Loyiha yaratilgach, chap menyudan **Project Settings** -> **Database** bo‘limiga kiring.
4. **"Connection string"** bandini toping, **URI** formatini tanlang:
   * Sizga quyidagicha havola beriladi:  
     `postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres`
   * `[YOUR-PASSWORD]` o‘rniga 2-bandda kiritgan parolingizni qo‘ying.
   * Ushbu havolani nusxalab oling (bu sizning `DATABASE_URL` ingiz bo‘ladi).

---

## 2-Qadam: Kodni GitHub ga yuklash

Loyihangiz papkasida terminal orqali:
```bash
git init
git add .
git commit -m "Grand CRM release"
git branch -M main
git remote add origin https://github.com/SIZNING_LOGININGIZ/grand-crm.git
git push -u origin main
```

---

## 3-Qadam: Bepul veb-serverda ishga tushirish (Koyeb yoki Render)

### A Variant — Koyeb.com (Tavsiya etiladi, tez va bepul)
1. **[Koyeb.com](https://www.koyeb.com)** ga kiring va ro‘yxatdan o‘ting.
2. **"Create App"** -> **"GitHub"** ni tanlang.
3. 2-qadamda yaratgan `grand-crm` repozitoriysini tanlang.
4. **Environment Variables** (Muhit o‘zgaruvchilari) bo‘limiga quyidagilarni kiriting:
   * `DATABASE_URL` = 1-qadamda Supabase dan olingan havola
   * `DEBUG` = `False`
   * `SECRET_KEY` = tasodifiy uzun qator (masalan, `super-secret-grand-crm-key-2026`)
   * `ALLOWED_HOSTS` = `*`
   * `TIME_ZONE` = `Asia/Tashkent`
   * `LANGUAGE_CODE` = `uz`
5. **"Deploy"** tugmasini bosing.
   * Koyeb avtomatik ravishda migratsiyalarni ishga tushiradi, statik fayllarni tayyorlaydi va saytni ishga tushiradi.
   * Sizga `https://grand-crm-xxxx.koyeb.app` ko‘rinishidagi bepul doimiy HTTPS manzil beriladi.

### B Variant — Render.com
1. **[Render.com](https://render.com)** ga kiring.
2. **"New +"** -> **"Web Service"** ni tanlang va GitHub repozitoriyingizni ulang.
3. Loyiha papkasida `render.yaml` fayli allaqachon tayyorlangan, u avtomatik ravishda barcha sozlamalarni o‘qib oladi.
4. Faqat `DATABASE_URL` ga Supabase havolasini kiritasiz va **"Create Web Service"** tugmasini bosasiz.

---

## 4-Qadam: Tizimga kirish

Server ishga tushgach, brauzeringizda sizga berilgan havolani ochasiz:
* **Ega (Owner) hisobi:**
  * Login: `owner`
  * Parol: `owner123`
* **Administrator hisobi:**
  * Login: `admin`
  * Parol: `admin123`

*Tizimga kirgach, birinchi navbatda sozlamalar bo‘limidan o‘zingizga yangi xavfsiz parol o‘rnatib oling.*
