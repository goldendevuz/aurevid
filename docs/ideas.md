# G'oyalar rejasi (backlog)

Raqiblar tahlili va suhbatlar davomida kelgan g'oyalar. Bu SPEC emas: g'oya bu yerga yoziladi,
qaror qilingandan keyin SPEC'ga ko'chiriladi va qurish boshlanadi.

**Qoidalar:** boshqa mahsulotdan kod, matn, nom va dizayn olinmaydi, faqat g'oya olinadi. Yangi
model yoki provayder kerak bo'lsa, avval `MODEL_LICENSES.md`ga yoziladi. Litsenziya noaniq bo'lsa,
default o'chiq bo'ladi.

**Ustuvorlik:** P1 = pul va o'sishga bevosita ta'sir qiladi; P2 = mahsulotni kuchaytiradi;
P3 = keyinroq.
**Hajm:** S = bir necha kun, M = 1-2 hafta, L = undan ko'p.

| # | G'oya | Nimaga kerak | Qayerdan | Ustuvorlik | Hajm | Eslatma |
|---|---|---|---|---|---|---|
| 1 | **Payme/Click orqali kredit paketlari** | Raqiblar $8-15/oy va xorijiy karta talab qiladi; mahalliy to'lov eng katta bo'shliq | Raqiblar tahlili | P1 | L | Webhook HMAC tayyor (`webhooks.py`) |
| 2 | ~~**Marketing yordamchisini asosiy funksiyaga aylantirish**~~ **Bajarildi** | Higgsfield foydalanuvchilarining ~85% i marketing qiladi | Higgsfield | P1 | M | Bajarildi: Landing'da reklama bo'limi, Studio'da "Reklama tayyorlash", biznes shablonlari, bir bosishda yaratish va "Hammasini yaratish" (narx oldindan ko'rsatiladi) |
| 3 | **Telegram bot** | O'zbekistonda asosiy kanal; tarqatish | Reja (SPEC 4.3) | P1 | L | Token asosidagi kirish kerak (`architecture.md`) |
| 4 | **Bitta prompt, bir nechta model, yonma-yon** | Foydalanuvchi qaysi model yaxshiroq ekanini bir bosishda ko'radi | AI SDK Image Generator | P2 | M | **Bajarildi:** Studio'dagi "Modellarni solishtirish" (2-4 model, har biriga alohida job, umumiy narx oldindan) |
| 5 | **Natijalarga avtomatik tavsif (alt text)** | Accessibility, galereya qidiruvi, mahsulot uchun reklama matni | AI Alt Text Generator, Vectr | P2 | S | Cloudflare Workers AI'dagi rasm→matn modeli; litsenziyani tekshirish |
| 6 | **Matn bilan rasmni tahrirlash** ("fonni oq qil", "logoni olib tashla") | Mahsulot rasmlari uchun eng ko'p so'raladigan ish | Gemini image editing | P2 | M | Model litsenziyasi: FLUX.1 Kontext [dev] tijoriy emas; ruxsat berilgan muqobil topish kerak |
| 7 | **Retseptlar: rasm → jonlantirish → 4K bitta zanjirda** | Hozir 3 ta alohida qadam; zanjir vaqtni tejaydi | Tersa (node kanvas) | P2 | M | **Bajarildi:** `POST /api/recipes/image-animate-4k/run`, zanjir job params'da, keyingi qadamni worker yaratadi (`services/recipes.py`) |
| 8 | **Model narxini oldindan ko'rsatish** ("≈ 4 kredit", "≈ $0.15") | Pullik modellarda ishonch | Tersa | P2 | S | **Bajarildi:** Studio va ModelPicker tanlov narxini (model × soni + upscale) va bepul ulushni ko'rsatadi (`frontend/src/pricing.ts`) |
| 9 | **Eskizdan rasm** | Kichik biznes maketni qo'lda chizadi | Scribble Diffusion | P3 | M | ControlNet bor provayder va litsenziya kerak |
| 10 | **Galereyada semantik qidiruv** ("qizil ko'ylakli reklama") | Galereya kattalashganda kerak | Vectr, Semantic Image Search | P3 | M | #5 ga bog'liq; ko'p tilli embedding modeli; SQLite'da oddiy kosinus |
| 11 | **Ovoz bilan prompt (o'zbekcha)** | Yozishni yoqtirmaydiganlar uchun | Live Transcription | P3 | S | Whisper o'zbek tilini qo'llaydi; Cloudflare'da bor, litsenziyani tekshirish |
| 12 | **Videoga uz/ru/en subtitr** | Reklama videolari ovozsiz ko'riladi | Mux AI workflows | P3 | M | ffmpeg imijda yo'q; Remotion permissive emas, ishlatilmaydi |
| 13 | **Jamoa tarifi (agentliklar uchun)** | Higgsfield B2B daromadi 10 barobar o'sgan | Higgsfield | P3 | L | Umumiy kredit, bir nechta a'zo |
| 14 | **Brend va mashhur shaxsga o'xshashlikni tekshirish** | Huquqiy xavfni kamaytiradi (GTA VI holati kabi) | Higgsfield Similarity Scoring | P3 | L | Chiqish moderatsiyasi bilan birga (`threat-model` "Known gaps") |

## Allaqachon bor (raqiblarda ham bor, bizda ham)

- Rasmni jonlantirish, navbat va progress (fal Video Generator): Studio, SSE, adolatli navbat.
- Endpoint bo'yicha rate limit (Mux namunasi): `ratelimit.py`, kunlik limit.
- Bir nechta provayder (AI SDK Image Generator): provayder registri.
