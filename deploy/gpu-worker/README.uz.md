# O'z GPU'ingizda bepul video (GPU worker)

Aurevid serveri video so'rovlarini navbatda ushlab turadi, sizning kompyuteringiz (GPU worker) esa
ularni olib, **o'z videokartasida** Wan 2.2 (Apache-2.0) bilan tayyorlaydi va serverga yuklaydi.
Bulutga pul to'lanmaydi: foydalanuvchilar uchun bu model **0 kredit** (kunlik job limiti saqlanadi).
Kompyuter o'chiq bo'lsa, video navbatda kutadi.

## Talablar

- NVIDIA GPU, **kamida 24 GB VRAM** (masalan RTX 3090/4090), so'nggi NVIDIA drayveri
- Docker va [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
  (`docker run --gpus all` ishlashi kerak)
- ~30 GB bo'sh joy (model ~20 GB, birinchi ishga tushirishda yuklanadi) va barqaror internet
- Serveringiz **https** orqali ochiq bo'lishi kerak

## 1. Serverda tokenni o'rnating

Uzun tasodifiy token yarating (kamida 32 belgi) va serverning `.env` fayliga yozing:

```bash
openssl rand -hex 32
```

```env
GPU_WORKER_TOKEN=<yuqorida chiqqan qiymat>
```

So'ng backend'ni qayta ishga tushiring. Token bo'sh bo'lsa, funksiya butunlay o'chiq (model
ro'yxatda ko'rinmaydi, `/api/gpu-worker/*` 404 qaytaradi). Tokenni gitga, chatga yoki
skrinshotga qo'ymang.

## 2. GPU kompyuterida worker'ni ishga tushiring

```bash
git clone https://github.com/goldendevuz/aurevid.git
cd aurevid
docker build -t aurevid-gpu-worker deploy/gpu-worker

docker run -d --name aurevid-gpu-worker --restart unless-stopped --gpus all \
  -e AUREVID_URL=https://sizning-domen.uz \
  -e GPU_WORKER_TOKEN=<o'sha token> \
  -v aurevid-hf-cache:/cache \
  aurevid-gpu-worker
```

Birinchi ishga tushirishda model yuklanadi (bir necha daqiqa). Holatni ko'rish:

```bash
docker logs -f aurevid-gpu-worker      # "model ready on ..." chiqsa, tayyor
```

## 3. Tekshiring

Studio → Video → **Wan 2.2 TI2V-5B (GPU worker)** ni tanlang, qisqa prompt yuboring. Log'da
`job ... generated in ... s` va `uploaded` chiqishi kerak; video tarixda paydo bo'ladi.
Bir klip odatda bir necha daqiqa oladi (GPU va qadamlar soniga bog'liq: `STEPS`, standart 20).

## Qanday ishlaydi

- Worker faqat **chiqish** so'rovlarini yuboradi (portlar ochilmaydi, router sozlash shart emas).
- Job olinganda 15 daqiqalik "ijara" (lease) beriladi. Worker o'chib qolsa, ijara tugagach job
  navbatga qaytadi; 3 marta urinishdan keyin job xato bilan tugaydi.
- Xatolik bo'lsa worker serverga xabar beradi, foydalanuvchiga umumiy xabar ko'rsatiladi.

## Xavfsizlik

- **Worker prompt'larni va foydalanuvchilarning yuklagan rasmlarini ko'radi.** Shuning uchun
  token faqat sizga (egasiga) tegishli kompyuterda turishi kerak. Boshqa odamga bermang:
  hozircha faqat egasining worker'iga ishoniladi.
- Token faqat `https` orqali yuboriladi (worker `http://` manzilni rad etadi, `localhost` bundan
  mustasno). Token boshqa joylarda ishlatilgan parol bo'lmasin.
- Token sizib chiqqan bo'lsa: serverda `GPU_WORKER_TOKEN`ni yangisiga almashtiring, backend'ni
  qayta ishga tushiring, worker'ni yangi token bilan qayta yarating
  (`docker rm -f aurevid-gpu-worker`, so'ng `docker run ...`).
- Server noto'g'ri token'ni 10 marta/daqiqadan ko'p rad etsa, IP vaqtincha bloklanadi.
- Konteyner oddiy (root bo'lmagan) foydalanuvchi bilan ishlaydi; kerak bo'lsa
  `--read-only --tmpfs /tmp` qo'shing.
- Modelning litsenziyasi: Wan 2.2 TI2V-5B, Apache-2.0, tijoriy foydalanish mumkin
  (`MODEL_LICENSES.md`).

## Muammolar

| Belgi | Sabab |
|---|---|
| `No CUDA GPU found` | `--gpus all` unutilgan yoki NVIDIA Container Toolkit o'rnatilmagan |
| `rejected GPU_WORKER_TOKEN (401)` | Ikki `.env`dagi token bir xil emas |
| `CUDA out of memory` | 24 GB dan kam VRAM yoki GPU'ni boshqa dastur band qilgan |
| Model Studio'da ko'rinmaydi | Serverda `GPU_WORKER_TOKEN` bo'sh yoki backend qayta ishga tushmagan |
| Video navbatda turibdi | Worker o'chiq yoki serverga ulana olmayapti (`docker logs`) |
