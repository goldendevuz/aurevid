# Aurevid

**Ochiq kodli, ko'p modelli AI rasm studiyasi: bitta prompt oynasi, avval bepul provayderlar, o'z kalitingiz ixtiyoriy.**

[English](README.md) · [Spetsifikatsiya](SPEC.md) · [Xavfsizlik](SECURITY.md) · [Deploy](docs/deploy.md)

## Nima qila oladi

- **Dark Studio v4 interfeysi**: Geist Variable shriftlariga asoslangan professional, yuqori zichlikdagi interfeys, 400-440px yopishqoq boshqaruv paneli, natijalar zichligi (2, 3 yoki 4 ustun), klaviatura bilan boshqariladigan lightbox modal oynasi, ommaviy yuklash/o'chirish imkoniyatiga ega kutubxona va mobil pastki panel.
- **Promptni boyitish (Expand Prompt)**: Bitta tugma orqali oddiy matnni boy kinoviy sahnalar, yorug'lik, kamera harakatlari va audio tasvirlariga ajratish (`POST /api/prompt/expand`), darhol bekor qilish (Undo).
- **Director rejimi (`/create?mode=director`)**: Rejissyorlik oqimi — chat uslubida g'oya kiritish, davomiylikni tanlash (5, 10, 15 soniya), tahrirlanadigan reja kartasi (boshlang'ich kadr, vaqt belgilari, rejissura va audio), oldindan aniq narx hisobi va bitta klip yoki ko'p sahnali Story'ga avtomatik yo'naltirish.
- **OpenRouter orqali 12 ta video modeli**: ByteDance Seedance v1 Pro/Lite, MiniMax Hailuo 01 / 2.3, Wan 2.1 T2V va I2V, Kling v1.6 Pro / Standard, Google Veo 2, OpenAI Sora, xAI Grok Imagine Video modellari va sentlarda ko'rsatiladigan shaffof narxlar.
- **Faol bo'lmagan modellar bo'limi**: ModelPicker'da ulanmagan modellarni ko'rsatish, texnik parametrlari, sentlardagi narxlari va to'g'ridan-to'g'ri o'z kalitini ulash havolalari.
- **Ko'p sahnali video**: 2-4 ta sahnani bitta yaxlit hikoyaga birlashtirish (`ffmpeg`), sahnalarni alohida qayta urinish.
- Prompt yozasiz, modelni tanlaysiz (har birida "Bepul" yoki "Pullik" belgisi va tijoriy foydalanish holati ko'rinadi)
- Nisbat, o'lcham va rasmlar soni (1-4)
- Video: matndan video va **Jonlantirish** (istalgan rasmingizdan video). Video uchun bepul servis
  topilmadi: o'z kalitingiz bilan fal.ai (Wan 2.2 5B, 5 soniyalik klip ≈ $0.15)
  yoki Modal (o'z GPU'ingizdagi Wan 2.2) orqali ishlaydi. O'zingizning videokartangiz bo'lsa,
  **GPU worker** (`deploy/gpu-worker/`) videoni bepul (0 kredit) tayyorlaydi: `GPU_WORKER_TOKEN` bilan yoqiladi. Faqat tijoriy foydalanishga aniq ruxsat
  berilgan modellar taklif qilinadi
- **4K / 8K rasmlar bepul**: serveringizning o'z CPU'sida ishlaydigan AI kattalashtirish
  (Real-ESRGAN, BSD-3). API ham, GPU ham kerak emas (8 yadroda o'lchangan: 4K ≈30 s, 8K ≈100 s, xotira ≈780 MB)
- Adolatli navbat: har bir foydalanuvchiga chegara, foydalanuvchilar orasida navbatma-navbat,
  og'ir CPU ishi bir vaqtda bitta, server to'lsa 429/503 bilan rad etadi; navbatdagi o'rin va vaqt ko'rinadi
- **Admin panel** (`/admin`): trendlar, foydalanuvchilar, joblar, voronka, retention,
  kogortalar, moderatsiya, tizim holati, provayder limitlari, e'lonlar, audit jurnali, CSV eksport
- Limitlarni o'zi o'rganish: limiti yozilmagan servislarda ishlatilganini sanaydi, limit xatolaridan
  o'rganadi va "bugun ≈N qoldi" ko'rsatadi
- 3 ta original kamera preseti
- Tarix galereyasi, sevimlilar, o'chirish, shikoyat
- Kreditlar: boshlang'ich bepul kreditlar, kunlik limit, xato bo'lsa kredit avtomatik qaytadi
- O'z API kalitingiz (BYOK): serverda shifrlangan holda saqlanadi, brauzerga hech qachon qaytmaydi
- Ma'lumotlarni yuklab olish va hisobni o'chirish
- Interfeys: o'zbek, rus, ingliz

## Tez boshlash (Docker, bitta buyruq)

```bash
git clone https://github.com/goldendevuz/aurevid.git && cd aurevid
docker compose up --build
```

http://localhost:8080 manzilini oching va ro'yxatdan o'ting. `.env` fayli bo'lmasa, loyiha **dev
rejimida** offline demo provayder bilan ishlaydi (haqiqiy AI emas, faqat sinov rasmi).

Haqiqiy rasm yaratish uchun (bepul):

1. https://dash.cloudflare.com da bepul hisob oching.
2. *My Profile → API Tokens* bo'limida faqat **Workers AI: Read** ruxsati bilan token yarating.
3. Account ID'ni dashboard'dan nusxalang.
4. Quyidagilarni bajaring:

```bash
cp .env.example .env
# .env ichida CF_ACCOUNT_ID, CF_API_TOKEN, JWT_SECRET va BYOK_ENCRYPTION_KEY ni to'ldiring
docker compose up --build
```

Cloudflare kuniga 10 000 "neuron" bepul beradi, bu taxminan 170 ta FLUX.1 schnell yoki 96 ta FLUX.2 klein 1024×1024 rasm (ikki model bitta kvotani bo'lishadi; ilova ehtiyotkorlik bilan kuniga 68 ta deb hisoblaydi, chunki alt matn ham shu kvotadan oladi).

> Docker *"all predefined address pools have been fully subnetted"* desa, eski Docker tarmoqlari
> ko'payib ketgan. Ro'yxatni `docker network ls` bilan ko'rib, keraksizlarini `docker network prune`
> bilan o'chiring.

## Dasturchilar uchun

```bash
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd frontend && npm ci && npm run dev     # http://localhost:5173
```

Testlar: `cd backend && uv run pytest -q`, `cd frontend && npm test`.

## Litsenziya

AGPL-3.0-or-later. O'zgartirilgan versiyani internet xizmati sifatida ishlatsangiz, foydalanuvchilarga
manba kodini taqdim etishingiz shart (`VITE_SOURCE_URL` ni sozlang).
