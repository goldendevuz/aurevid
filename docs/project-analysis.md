# Aurevid: loyiha tahlili (2026-11-19)

Bu hujjat README, SPEC, `docs/` va litsenziya fayllari asosida yozilgan. Belgilar:

- **[hujjat]**: repodagi fayllarda aniq yozilgan.
- **[taxmin]**: hujjatda yozilmagan, tahlilchining xulosasi. Qaror qilishdan oldin tekshiring.

## 1. Bu qanday loyiha?

**Aurevid** ochiq kodli, ko'p modelli AI studiya. Bitta prompt oynasi bor, rasm va video yaratadi.
Avval bepul provayderlardan foydalanadi, foydalanuvchi xohlasa o'z API kalitini ulaydi. **[hujjat]**

## 2. Nima qiladi?

- Matndan rasm yaratadi. Nisbat (1:1, 16:9, 9:16, 4:3, 3:4), o'lcham va 1-4 ta natija tanlanadi.
- Matndan video yaratadi. **Jonlantirish** (Animate) istalgan rasmni videoga aylantiradi.
- 4K/8K rasmni bepul beradi. Real-ESRGAN serverning o'z CPU'sida ishlaydi, GPU ham, API ham kerak emas.
  8 yadroda o'lchangan: 4K taxminan 30 s, 8K taxminan 100 s, xotira taxminan 780 MB.
- 4K/8K video ixtiyoriy va pullik (fal.ai'da Topaz, foydalanuvchining o'z kaliti bilan).
- 3 ta original kamera preseti: Gentle Drift In, Halo Orbit, Skyward Unveil.
- Tarix galereyasi: sevimlilar, Remix (promptni qayta ishlatish), o'chirish, shikoyat.
- Kreditlar: boshlang'ich 50 kredit, kunlik limit (30 job), xato bo'lsa avtomatik qaytarish.
- Adolatli navbat: foydalanuvchi boshiga chegara, navbatma-navbat bajarish, bir vaqtda bitta og'ir CPU ishi,
  server to'lsa 429/503, navbatdagi o'rin va taxminiy vaqt ko'rinadi.
- Admin panel (`/admin`): trendlar, foydalanuvchilar, joblar, voronka, retention, kogortalar, moderatsiya,
  tizim holati, provayder limitlari, e'lonlar, audit jurnali, CSV eksport.
- Marketing yordamchisi (`/marketing`): mahsulot rasmi yoki matnidan 9:16 va 1:1 reklama promptlari,
  bepul offline shablonlar va ixtiyoriy AI sayqal (SPEC 4.1).
- Interfeys: o'zbek, rus, ingliz.

## 3. Nimaga kerak?

**[hujjat]** Kichik biznes va kontent yaratuvchilar (avval O'zbekiston, keyin xalqaro) bitta qulay joyda,
murakkab sozlamalarsiz, arzon yoki bepul rasm/video olishi uchun. Har bir modelda "Bepul/Pullik" va
"tijoriy foydalanish mumkinmi" belgisi ko'rsatiladi.

**[taxmin]** Bozordagi muammolar: obunalar qimmat, interfeys o'zbek tilida emas, qaysi natijani tijoriy
ishlatish mumkinligi tushunarsiz.

## 4. Raqiblar kim?

Hujjatlarda raqiblar ro'yxati **yo'q**. Quyidagisi **[taxmin]**:

| Guruh | Misollar | Farqi |
|---|---|---|
| Yopiq, pullik xizmatlar | Midjourney, Leonardo, Ideogram, Adobe Firefly, Canva Magic Media; video: Runway, Kling, Pika, Higgsfield | Sifati yuqori, lekin obuna pullik, o'zbek tili yo'q |
| Ochiq kodli, o'zi o'rnatiladigan | ComfyUI, Automatic1111, Fooocus, InvokeAI, Open WebUI | Kuchli, lekin o'rnatish uchun texnik bilim va GPU kerak |
| Bepul yengil xizmatlar | Pollinations, Craiyon, Bing Image Creator | Oddiy, lekin cheklangan, tijoriy shartlari noaniq |

SPEC bo'limi "Research note"ga ko'ra, spetsifikatsiya boshqa bir sayt (AI video, rasm va ovoz studiyasi
deb tasvirlangan) asosida yozilgan, lekin uning funksiyalari nusxalanmagan: spetsifikatsiya faqat egasining
topshirig'iga tayanadi.

## 5. Nimaga aynan bizning loyiha?

- O'zbek tili birinchi darajali til sifatida qo'llab-quvvatlanadi. **[hujjat]**
- Faqat litsenziyasi aniq modellar yoqilgan. Qoida: "unclear → off by default" (`MODEL_LICENSES.md`). **[hujjat]**
- 4K/8K rasm bepul, GPU'siz. **[hujjat]**
- Limitlarni o'zi o'rganadi: provayder xatolaridan "bugun taxminan N ta qoldi"ni hisoblaydi. **[hujjat]**
- Xavfsizlik: threat model, IDOR testlari, SSRF himoyasi, shifrlangan BYOK kalitlari, argon2id, CSRF. **[hujjat]**
- Arzon joylashtirish: bitta VPS, Docker, Cloudflare Tunnel. **[hujjat]**

## 6. Nimaga open source?

Litsenziya **AGPL-3.0-or-later**. Sababi hujjatda aniq yozilmagan. Mantiqiy sabablar **[taxmin]**:

- Foydalanuvchi o'z serveriga o'rnatib, ma'lumotini o'zida saqlashi mumkin.
- Ishonch: kalitlar qayerga ketishi kod orqali tekshiriladi.
- AGPL kodni yopib, o'z servisi qilib sotib yuborishdan himoya qiladi: o'zgartirilgan versiya
  tarmoq xizmati sifatida ishlasa, manba kodini foydalanuvchilarga berish shart (`VITE_SOURCE_URL`).
- Hamjamiyat hissa qo'shishi mumkin (`CONTRIBUTING.md`).

## 7. Qaysi platformalar uchun?

- **Hozir:** faqat web (React SPA). **[hujjat]**
- **Rejada:** Telegram bot, desktop (Tauri), PWA, brauzer kengaytmasi. Hammasi bitta `/api`dan foydalanadi. **[hujjat]**
- Native iOS/Android ilova rejada yo'q. PWA unga yaqin yechim. **[taxmin]**

## 8. Nimaga bepul?

**[hujjat]** Talab: ishlab chiqish va birinchi foydalanuvchilar uchun bepul, majburiy pullik servis yo'q.
Bepullik mexanizmi:

- Rasm: Cloudflare Workers AI bepul kvotasi (kuniga 10 000 Neuron, taxminan 170 rasm, hisob boshiga).
- 4K/8K: serverning o'z CPU'si.
- Pullik narsalar (video, fal.ai): foydalanuvchining **o'z kaliti** orqali, loyiha egasi to'lamaydi.

**Cheklov:** bepul video provayder topilmadi. Hozir pullik to'lov (Payme/Click) yo'q, faqat boshlang'ich
kreditlar bor. Pul ishlash modeli hali belgilanmagan. Bu ochiq savol.

## 9. Maqsad nima?

**[hujjat]** Kichik biznes va yaratuvchilarga bitta joyda sodda, ko'p tilli, bepul-birinchi AI studiya berish.

**[taxmin]** Qo'shimcha: portfolio loyiha, O'zbekiston bozorida erta kirish, ochiq kod orqali jamoa yig'ish.

## 10. Kelajakdagi rejalar

**[hujjat]** SPEC bo'lim 4 va 5 hamda `docs/` bo'yicha:

- Payme/Click orqali to'lovlar
- Telegram bot, desktop (Tauri), PWA, brauzer kengaytmasi
- Magic link va Telegram orqali kirish
- Replicate provayderi
- R2 saqlash adapteri
- SQLite o'rniga PostgreSQL (masshtab uchun)
- Chiqish rasmlarini tekshiradigan moderatsiya modeli
- Ovoz generatsiyasi: hozircha noma'lum, loyiha doirasidan tashqari

## 11. Zaif tomonlar va xavflar

`docs/threat-model.md` "Known gaps" va `MODEL_LICENSES.md` bo'yicha:

| Xavf | Izoh |
|---|---|
| Chiqish rasmlari moderatsiyasi yo'q | Kalit so'zli filtrni aylanib o'tish oson. Ommaviy ro'yxatdan o'tishni ochishdan oldin hal qilish kerak |
| Email tasdiqlash va parolni tiklash yo'q | Email provayder yoki magic link kerak |
| Bepul video yo'q | Mahsulotning eng katta bo'shlig'i |
| Bepul kvota kichik | Taxminan 170 rasm/kun, hisob boshiga. Foydalanuvchilar ko'paysa yetmaydi |
| Tijoriy litsenziya noaniq | Pollinations, Kling, Seedance, Topaz: tijoriy ishga tushirishdan oldin qayta tekshirish kerak |
| SQLite | Yozuvlar ketma-ket bajariladi, kichik beta uchun yetarli, masshtab uchun PostgreSQL kerak |
| Fayllar shifrlanmagan | Lokal diskdagi rasmlar shifrlanmagan: shifrlangan volume yoki R2 SSE |
| Nom | Google "Aurevid"ni "ayurvedic"ga tuzatishi mumkin. Sarlavhalarda "AI studio" bilan birga ishlatiladi |
| Mualliflik huquqi | GTA VI namunalari huquqiy sabab bilan olib tashlangan. Dizaynda faqat kayfiyat olinadi, logo, shrift va nom olinmaydi |
| Vaqtinchalik dizayn | Neon Coast (quyosh, palmalar, grid) trenddagi kayfiyat uchun prod'ga qo'yilgan vaqtinchalik dizayn; keyingi oy redesign bo'lishi mumkin (`docs/design.md`) |
| Faqat tijoriy ruxsatli modellar | 2026-11-20 dan tijoriy foydalanishi noaniq yoki cheklangan modellar (Pollinations video, Kling, Topaz) kodda yashirilgan; prod'da yoqib bo'lmaydi (`MODEL_LICENSES.md`, 3-qoida) |

## Xulosa

Loyiha texnik jihatdan puxta: xavfsizlik, navbat, admin panel va litsenziya nazorati ishlab chiqilgan.
Biznes jihatdan eng zaif joylar: pul ishlash modeli yo'q, bepul video yo'q, o'zbek tilidagi auditoriya
hajmi o'lchanmagan.
