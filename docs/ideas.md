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
| 4 | **Bitta prompt, bir nechta model, yonma-yon** | Foydalanuvchi qaysi model yaxshiroq ekanini bir bosishda ko'radi | AI SDK Image Generator | P2 | M | Kredit = modellar yig'indisi; bepul modellar bilan arzon |
| 5 | ✅ **Natijalarga avtomatik tavsif (alt text)** | Accessibility, galereya qidiruvi, mahsulot uchun reklama matni | AI Alt Text Generator, Vectr | P2 | S | **Bajarildi (2026-11-20):** Qwen 3.8 27B (Apache-2.0), tafsilotlar oynasida nusxalash tugmasi bilan; `img alt` |
| 6 | ✅ **Matn bilan rasmni tahrirlash** ("fonni oq qil", "logoni olib tashla") | Mahsulot rasmlari uchun eng ko'p so'raladigan ish | Gemini image editing | P2 | M | **Bajarildi (2026-11-20):** FLUX.2 [klein] 4B (Apache-2.0), "Matn bilan tahrirlash" tugmasi; FLUX.1 Kontext [dev], FLUX.2 [dev] va klein 9B tijoriy emas |
| 7 | **Retseptlar: rasm → jonlantirish → 4K bitta zanjirda** | Hozir 3 ta alohida qadam; zanjir vaqtni tejaydi | Tersa (node kanvas) | P2 | M | To'liq node kanvas emas, tayyor zanjirlar; navbatda ketma-ket joblar |
| 8 | **Model narxini oldindan ko'rsatish** ("≈ 4 kredit", "≈ $0.15") | Pullik modellarda ishonch | Tersa | P2 | S | `ModelInfo`ga narx maydoni |
| 9 | **Eskizdan rasm** | Kichik biznes maketni qo'lda chizadi | Scribble Diffusion | P3 | M | ControlNet bor provayder va litsenziya kerak |
| 10 | **Galereyada semantik qidiruv** ("qizil ko'ylakli reklama") | Galereya kattalashganda kerak | Vectr, Semantic Image Search | P3 | M | #5 ga bog'liq; ko'p tilli embedding modeli; SQLite'da oddiy kosinus |
| 11 | ✅ **Ovoz bilan prompt (o'zbekcha)** | Yozishni yoqtirmaydiganlar uchun | Live Transcription | P3 | S | **Bajarildi (2026-11-20):** Whisper large-v3-turbo (MIT), mikrofon tugmasi, 30 soniya chegarasi |
| 12 | **Videoga uz/ru/en subtitr** | Reklama videolari ovozsiz ko'riladi | Mux AI workflows | P3 | M | ffmpeg imijda yo'q; Remotion permissive emas, ishlatilmaydi |
| 13 | **Jamoa tarifi (agentliklar uchun)** | Higgsfield B2B daromadi 10 barobar o'sgan | Higgsfield | P3 | L | Umumiy kredit, bir nechta a'zo |
| 14 | **Brend va mashhur shaxsga o'xshashlikni tekshirish** | Huquqiy xavfni kamaytiradi (GTA VI holati kabi) | Higgsfield Similarity Scoring | P3 | L | Chiqish moderatsiyasi bilan birga (`threat-model` "Known gaps") |
| 15 | **Ovozli video: litsenziyasiz (CC0) musiqa kutubxonasi** | Modal kliplari ovozsiz; MMAudio tijoriy emas (CC-BY-NC) | To'y videosi tahlili | P2 | M | Faqat CC0/public-domain treklar; ffmpeg bilan videoga ulash (imijga ffmpeg qo'shish yoki Modal'da) |
| 16 | **Hamjamiyat GPU worker'lari** (ishonchli odamlar o'z GPU'sida video tayyorlaydi) | Bulut narxisiz bepul video; foydalanuvchilar GPU'sini ulashadi | Egasining GPU worker'i (`deploy/gpu-worker/`) | P2 | M | 1-bosqich: faqat egasining worker'iga ishoniladi (worker prompt va rasmlarni ko'radi). Keyin: worker'ga alohida token, ro'yxatdan o'tkazish, natijani tekshirish, to'lov/mukofot; bitta umumiy token buning uchun yetarli emas |
| 17 | **15 soniyalik video: 5 soniyalik klip zanjiri** | Wan 2.2 5B bir yo'la 361 kadrda "qulaydi" (sinab ko'rildi 2026-11-21: ko'k dog' va qora ekran), shuning uchun uzun video faqat oldingi klipning oxirgi kadridan davom ettirib yig'ilishi mumkin | Raqiblar (uzun video) | P2 | M | Avval bitta tajriba video, kadrlarini tekshirib, keyin saytga. Narxi ~3x. LTX-2.3 muqobil (litsenziyasi shartli) |
| 18 | **Ko'p sahnali video** (ssenariy → 2-4 ta 5 s sahna → `ffmpeg` bilan biriktirish, ixtiyoriy ovoz/subtitr) | 15 s muammosining halol yechimi; #17 bilan birga. Manba g'oyalar: lcy362/agnes-video-generator va free-short-video-studio (MIT; brauzerda `ffmpeg.wasm` bilan biriktirish, serverga yuk tushmaydi). | **Bajarildi (PR kutilmoqda, 2026-11-21):** `/create`da Video → "Ko'p sahnali"; har sahna oddiy 5 s job (`stories` jadvali, `Job.story_id`), hammasi tayyor bo'lgach worker `ffmpeg` bilan biriktiradi (`services/stitch.py`, `services/stories.py`). Narx, kunlik limit va bepul ulush hamma sahna uchun oldindan tekshiriladi (yo'q yoki hammasi). Xato sahnani qayta yaratish mumkin. Eslatma: `MAX_ACTIVE_JOBS_PER_USER=3` bo'lsa 4 sahnali video rad etiladi. Ovoz/subtitr hali yo'q. |
| 19 | **BYOK provayderlar: Agnes (bepul kalit) va Vercel AI Gateway** | Foydalanuvchi o'z kalitini kiritadi, biz to'lamaymiz (`resolve_credentials`). Agnes bepulligi uchinchi tomon aksiyasi; shartlari o'qilmaguncha `commercial_use="unclear"` (yashirin). Gateway bitta adapter bilan Veo/Kling/Wan'ni beradi, $10 depozit kerak. |
| 20 | **GPU'siz "tushuntiruvchi video" rejimi** (stok-kadr + TTS + subtitr) | OpenMontage (AGPL-3.0) g'oyasi: Archive.org/NASA/Pexels kadrlari, Piper TTS, Remotion. Avval o'zbek tilida yaxshi TTS ovozi borligini tekshirish kerak. Pullik so'rovni qayta yubormaslik uchun "resume job" naqshi ham foydali. |
| 21 | **Post-production qatlami: kamera harakati + LUT + soundscape** (generatsiya qilingan klip/rasm ustiga) | goldendevuz/aurevid-aistudio (Kinoframe) g'oyasi: dolly zoom/orbit kabi harakatlar, 6 ta rang LUT, 4 ta linza, ovoz muhiti, brauzerda WebM eksport. Modelsiz, GPU'siz, arzon. Ko'p sahnali videoga (#18) sahnalar orasida o'tish/rang uyg'unligi sifatida ham mos. Manba kodi litsenziyasini avval tekshirish kerak. |

## Allaqachon bor (raqiblarda ham bor, bizda ham)

- Rasmni jonlantirish, navbat va progress (fal Video Generator): Studio, SSE, adolatli navbat.
- Endpoint bo'yicha rate limit (Mux namunasi): `ratelimit.py`, kunlik limit.
- Bir nechta provayder (AI SDK Image Generator): provayder registri.
