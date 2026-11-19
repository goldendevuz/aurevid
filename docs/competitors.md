# Raqiblar tahlili (2026-11-19)

Maqsad: real bozordagi raqiblarning raqamlarini bir joyga yig'ish va Aurevid bilan solishtirish.
Asosiy raqib: **Higgsfield**.

**Belgilar:**
- **[manba]**: raqam quyidagi manbalardan olingan, sana ko'rsatilgan.
- **[baho]**: tahlilchi (Sacra) bahosi, kompaniyaning rasmiy raqami emas.
- **[taxmin]**: bizning xulosamiz.

Barcha raqamlar 2026-11-19 holatiga ko'ra. Xususiy kompaniyalarning raqamlari ko'pincha ularning
o'z bayonotlari, auditdan o'tmagan.

## 1. Qisqa xulosa

- Bozor juda tez o'smoqda. Higgsfield 2026-yil oktabrda yillik daromad sur'ati (annualized revenue)
  bo'yicha **$1.35B** ga yetgan. Bu Runway ($450M kutilmoqda) va Kling (~$500M) dan yuqori. **[manba]**
- G'olib model: **agregator**. Boshqa laboratoriyalarning modellarini (Kling, Seedance, Veo, Flux) bitta
  interfeysda yig'ish, kredit va obuna bilan sotish. Higgsfield va OpenArt aynan shunday ishlaydi.
  Aurevid arxitekturasi ham agregator, demak yo'nalish to'g'ri. Bizda pul olish mexanizmi yo'q. **[taxmin]**
- Higgsfield foydalanuvchilarining ~85% i **ijtimoiy tarmoq va marketing mutaxassislari**. Bu Aurevid'ning
  maqsadli auditoriyasi (kichik biznes, kontent yaratuvchilar) bilan bir xil. **[manba]**
- Ochiq kodda eng yaqin raqib: **Open-Generative-AI** (35k yulduz, MIT). U "senzurasiz" va pullik
  MuAPI'ga yo'naltiradi. Bizning farqimiz: xavfsizlik, litsenziya shaffofligi, o'zbek va rus tillari. **[taxmin]**
- Video eng qimmat qism. Sora kuniga ~$1M sarflagan, Stability AI choraklik daromadi $5M dan kam
  va katta zarar ko'rmoqda. Video'ni kreditlarsiz bepul berish halokatli. **[manba]**

## 2. Asosiy raqib: Higgsfield

| Ko'rsatkich | Qiymat | Sana | Belgi |
|---|---|---|---|
| Asos solingan | 2023, San-Fransisko; CEO: Alex Mashrabov | | [manba] |
| Yillik daromad sur'ati | $700M (avgust) → $1B (sentabr) → **$1.35B** (oktabr) | 2026 | [manba] |
| Foydalanuvchilar | **32M+**, ~**1M** pullik obunachi | 2026-09 | [manba] |
| Auditoriya | ~85% ijtimoiy tarmoq va marketing, ulardan 80% tijoriy ish qiladi | 2026-01 | [manba] |
| Daromad tuzilmasi | Obuna 90% dan ~60% ga tushgan, qolgani qo'shimcha kredit xaridlari | 2026 | [manba] |
| B2B | Biznes shartnomalari daromadi iyundan beri 10 barobar o'sgan | 2026 | [manba] |
| Investitsiya | $50M Series A (2025-09), $80M (2026-01, baho $1.3B+), **$400M Series B** (2026-08, baho **$5.4B**). Jami $538M | 2026-08 | [manba] |
| Tariflar | Free (tanlangan modellar, oylik kredit yo'q, bir vaqtda 1 ta generatsiya), Basic, Pro, Ultimate, Creator; Team; kredit paketlari; "Unlimited" ayrim tariflarda | 2026-11 | [manba]; aniq narxlar sahifada JS bilan yuklanadi, tekshirilmadi |
| Mahsulot | Rasm, video, ovoz; Cinema Studio; nomli kamera presetlari kutubxonasi; AI agent; API (open.higgsfield.ai); MCP; mobil | 2026-11 | [manba] |
| Xavfsizlik | Team tarifida "Similarity Scoring": tanilgan qahramon, mashhur shaxs va logolarga o'xshashlikni tekshiradi | 2026-03 | [manba] |

**Aurevid uchun xulosa [taxmin]:** Higgsfield bilan sifat yoki modellar soni bo'yicha raqobatlashib
bo'lmaydi. Raqobat qilish mumkin bo'lgan joylar: mahalliy til, mahalliy to'lov (Payme/Click), arzon narx,
o'z serveringizda ishlatish va litsenziya shaffofligi.

## 3. Pul topayotgan yopiq servislar

### 3.1. Agregatorlar va video/rasm studiyalari (to'g'ridan-to'g'ri raqiblar)

| Servis | Daromad | Foydalanuvchilar | Investitsiya / baho | Narx | Manba |
|---|---|---|---|---|---|
| **Higgsfield** | $1.35B sur'at (2026-10) | 32M+, ~1M pullik | $538M; $5.4B | Free + 4 tarif | Sacra |
| **OpenArt** | $70M ARR (2025 oxiri; 2024: $10.5M) | 8M MAU, 20 xodim (2026-01) | $35M jami | $14–$240/oy, 100+ model | Sacra |
| **Kling AI** (Kuaishou) | ~$500M sur'at (2026-03) **[baho]**; 2026 Q1: 650M yuan (+300%) **[manba]** | 60M+ ro'yxatdan o'tgan, 30k+ korporativ mijoz | $2.8B (2026-07), baho $15–18B | $10–$179.99/oy | Sacra, Kuaishou hisoboti |
| **Runway** | $100M (2026-04), yil oxiriga $450M kutilmoqda | 60M+ "creator" | ~$1.05B jami; $5.3B (2026-02) | $76/oygacha | Sacra, Wikipedia |
| **Midjourney** | $200M+ ARR **[baho, eski]** | ~21M Discord a'zosi, ~1.4M pullik **[baho]** | Tashqi investitsiya yo'q | $10–$120/oy (Basic'dan boshlanadi) | Sacra |
| **Magnific** (sobiq Freepik) | ~$230M ARR (2026-04), yarmi videodan | 1M+ pullik obunachi | | | Wikipedia |
| **MiniMax / Hailuo** | $800M sur'at (2026-08), 2026 H1: $116.6M | (eski: 11M MAU) | Birjada, ~$8.2B | Hailuo: 6–10 s klip | Sacra, Wikipedia |
| **Luma (Dream Machine)** | Ma'lumot yo'q | Yangi foydalanuvchilar faqat Luma Agents orqali (2026-09) | $900M Series C (2025-11) | Unlimited $30/oy (2025) | Sacra, Wikipedia |
| **Pika** | Ma'lumot yo'q | 500k+ (eski) | $135M jami | Free 80 kredit; $8–$76/oy | Sacra |
| **Ideogram** | Ma'lumot yo'q | | $16.5M seed + $80M (2024) | | Wikipedia |

### 3.2. Avatar va korporativ video (qo'shni bozor)

| Servis | Daromad | Mijozlar | Baho | Manba |
|---|---|---|---|---|
| Synthesia | ~$140M ARR (2026-02), 2026 da $200M kutilmoqda | 65k+, 70% daromad korporativ | $4B (2026-01) | Sacra, Wikipedia |
| HeyGen | $123M ARR (2025 oxiri) | SMB va yaratuvchilar | $500M (2023), $74M jami | Sacra |

### 3.3. Katta platformalar (AI qo'shimcha funksiya sifatida)

| Platforma | Raqamlar | Manba |
|---|---|---|
| Canva | 265M+ MAU, 31M+ pullik, ARR $4B (2025 oxiri); baho $42B; 2026-08 da o'sish prognozi 30% dan 20% ga tushirilgan | Wikipedia |
| Lightricks (LTX) | $250M ARR (2025-07); LTX-Video ochiq model | Wikipedia |
| Adobe Firefly, Google Veo, OpenAI Sora, Meta AI | Alohida daromad e'lon qilinmagan; o'z ekotizimlariga bepul yoki obuna ichida beriladi | Wikipedia |

### 3.4. Model laboratoriyalari (biz ularning API'sidan foydalanamiz, raqib emas)

| Laboratoriya | Raqamlar | Manba |
|---|---|---|
| Black Forest Labs (Flux) | $300M Series B, $3.25B (2025-12); Meta bilan $140M, Adobe/Canva/Snap bilan ~$300M shartnoma | Sacra |
| Alibaba Wan | Wan 2.2 ochiq (Apache-2.0), 18.8k yulduz | GitHub |

## 4. Pul topa olmayotgan yoki qiynalayotganlar

| Servis | Muammo | Manba |
|---|---|---|
| Stability AI | Choraklik daromad $5M dan kam, katta xarajat; Getty bilan sud jarayoni | Sacra, Wikipedia |
| OpenAI Sora | Foydalanuvchilar ~1M dan 500k dan kamga tushgan, xarajat kuniga ~$1M | Wikipedia |
| Pika | $135M investitsiya, daromad e'lon qilinmagan, foydalanuvchilar soni kichik | Sacra |
| Midjourney (sekinlashish xavfi) | Faqat obuna, video kech qo'shilgan; Canva va Microsoft bepul tarqatadi | Sacra |

**Saboq [taxmin]:** video xarajati juda katta. Kreditsiz "cheksiz bepul video" bergan servislar
zarar ko'radi. Aurevid'ning "video faqat foydalanuvchi kaliti bilan" qoidasi to'g'ri.

## 5. Ochiq kodli raqiblar (GitHub, 2026-11-19)

| Loyiha | Yulduz | Litsenziya | Kim uchun | Aurevid'dan farqi |
|---|---|---|---|---|
| AUTOMATIC1111 SD WebUI | 165k | AGPL-3.0 | O'z GPU'si bor texnik foydalanuvchi | Oxirgi push 2026-03, sekinlashgan |
| Open WebUI | 159k | Custom | LLM chat (rasm qo'shimcha) | Asosan chat |
| **ComfyUI** | 148k | GPL-3.0 | Node graf, kuchli va murakkab | 4M+ foydalanuvchi; kompaniya $16.2M+ olgan; GPU kerak |
| Fooocus | 54k | GPL-3.0 | Oddiy SDXL interfeysi | Oxirgi push 2025-12, deyarli to'xtagan |
| **Open-Generative-AI** | **35k** | MIT | 600–800+ model, "senzurasiz" studiya | **Eng yaqin OSS raqib.** Pullik MuAPI orqali ishlaydi va "white label" ($49/oy dan) sotadi; filtr yo'q |
| Open-Sora | 30k | Apache-2.0 | Video model | Model, studiya emas |
| InvokeAI | 29k | Apache-2.0 | Professional rassomlar | GPU kerak |
| Wan 2.2 | 19k | Apache-2.0 | Video model | Biz Modal va fal orqali ishlatamiz |
| HunyuanVideo / WanGP / LTX-Video | 13k / 12k / 11k | turli | Video modellar / "GPU poor" UI | Lokal GPU kerak |
| Pollinations | 5.3k | MIT | Bepul API platforma | Biz provayder sifatida ishlatamiz |
| SwarmUI | 4.8k | MIT | Lokal SD UI | GPU kerak |
| **Aurevid** | **2** | AGPL-3.0 | Kichik biznes, uz/ru/en | Repo 2026-11-17 da ochilgan |

## 5a. Vercel shablonlari (ochiq kodli namuna ilovalar)

Bular to'liq mahsulot emas, bitta funksiyani ko'rsatadigan namunalar. Hammasi Next.js va Vercel
infratuzilmasiga (Blob, KV, Postgres, Workflow, AI Gateway) bog'langan. Hisob, kredit, navbat,
moderatsiya va ko'p tillilik yo'q. Ular foydalanuvchi emas, **dasturchi** uchun raqib: "o'zim AI studiya
qilaman" degan odam shulardan boshlashi mumkin. Biz ulardan kod olmaymiz, faqat g'oya olamiz
(ayrimlarida litsenziya fayli yo'q, `NOASSERTION`). Statistika: GitHub API, 2026-11-19.

| Shablon | Nima qiladi | Repo, yulduz, litsenziya | Aurevid'ga aloqasi |
|---|---|---|---|
| AI Alt Text Generator | Rasmga AI tavsif yozadi (BLIP) | `vercel/examples` ichida, MIT | **Bor**: natijalarga avtomatik tavsif (SEO, qidiruv, reklama matni) |
| AI SDK Image Generator | Bitta prompt bir vaqtda bir nechta provayderga (Replicate, Fireworks, Vertex, OpenAI) | vercel-labs, 113, litsenziya ko'rsatilmagan | **To'g'ridan-to'g'ri**: bizning "bitta prompt oynasi"ga eng yaqin. Farqi: parallel solishtirish |
| Scribble Diffusion | Qo'lda chizilgan eskizdan rasm (ControlNet, Replicate) | repo endi mavjud emas (404) | **Bor**: eskizdan rasm, kichik biznes uchun maket |
| fal Image Generator | fal + AI SDK bilan rasm | vercel-labs, 32, arxivlangan | Bizda bor (fal provayderi) |
| Gemini 2.0 Flash image gen/edit | Matn bilan rasmni tahrirlash, suhbat tarixi bilan | google-gemini, 541, Apache-2.0, arxivlangan (model o'chirilgan) | **Bor**: suhbat orqali tahrirlash |
| Tersa | Node'li kanvas: matn, rasm, video modellarini ulab workflow qurish, 25+ provayder, narx ko'rsatkichi | vercel-labs, **1 046**, MIT | **Bor**: zanjirlar (rasm → jonlantirish → 4K) va model narxini ko'rsatish |
| Vectr | Yuklangan rasmga AI tavsif, keyin semantik qidiruv (Upstash) | vercel-labs, 113, MIT | **Bor**: galereyada "qizil ko'ylakli reklama" deb qidirish |
| Semantic Image Search | pgvector bilan rasm qidiruvi | vercel-labs, 235, litsenziya ko'rsatilmagan | Vectr bilan bir xil g'oya |
| fal Video Generator | Rasmni jonlantirish, navbat va progress | fal-ai-community, 19, MIT | Bizda bor (Jonlantirish, SSE, navbat) |
| Next.js Live Transcription | Deepgram bilan real vaqtda nutqni matnga | deepgram-starters, 270, MIT | **Qisman**: ovoz bilan prompt yozish |
| Mux AI + Vercel Workflows | Videoga subtitr, tarjima, dublyaj, xulosa va teglar; Remotion bilan klip | muxinc, 18, litsenziya ko'rsatilmagan | **Bor**: reklama videosiga uz/ru/en subtitr. Remotion permissive emas, ishlatilmaydi |

**Xulosa [taxmin]:** hech biri Aurevid'ning to'liq o'rnini bosmaydi. Bizda bor narsalar (navbat, kredit,
admin, moderatsiya, uz/ru, o'z serverida ishlash) ularda yo'q. Ular esa bizda yo'q 6 ta foydali g'oyani
ko'rsatdi; ular [`docs/ideas.md`](ideas.md) ga yozildi.

## 6. Aurevid bilan solishtirish

| Xususiyat | Higgsfield | OpenArt | Midjourney | ComfyUI | Open-Generative-AI | **Aurevid** |
|---|---|---|---|---|---|---|
| Bepul foydalanish | Free tarif (oylik kredit yo'q) | Tekshirilmagan | Tekshirilmagan ($10 dan) | Ha (o'z GPU'si) | Ha, lekin MuAPI kaliti pullik | **Ha**: Cloudflare kvotasi + 50 kredit |
| Bepul video | Yo'q | Tekshirilmagan | Yo'q | O'z GPU'si bilan | Yo'q | **Yo'q** (faqat o'z kaliti bilan) |
| 4K/8K rasm | Upscale, kredit evaziga | Tekshirilmagan | Upscale | Ha (GPU) | API orqali | **Bepul, CPU'da** |
| Modellar soni | O'nlab | 100+ | Faqat o'zi | Cheksiz | 600–800+ | Bir nechta |
| Kamera presetlari | Katta kutubxona | Tekshirilmagan | Yo'q | Node'lar | Bor | 3 ta original |
| O'zbek/rus interfeysi | Tekshirilmagan | Tekshirilmagan | Tekshirilmagan | Yo'q | Tekshirilmagan | **Ha (uz/ru/en)** |
| Mahalliy to'lov (Payme/Click) | Yo'q **[taxmin]** | Yo'q **[taxmin]** | Yo'q **[taxmin]** | – | – | Rejada |
| Tijoriy litsenziya belgisi | Tekshirilmagan | Tekshirilmagan | Tarifga bog'liq | Yo'q | Yo'q | **Har bir modelda** |
| Moderatsiya | Bor + Similarity Scoring | Tekshirilmagan | Bor | Yo'q | **Yo'q (senzurasiz)** | Kalit so'z filtri, shikoyat, admin |
| O'z serverida ishlatish | Yo'q | Yo'q | Yo'q | Ha | Ha | **Ha (Docker, navbat, admin)** |
| Pul ishlash modeli | Obuna + kredit + B2B | Obuna + kredit | Obuna | Bulut xizmati | MuAPI white label | **Yo'q** |

## 7. Aurevid uchun imkoniyatlar [taxmin]

1. **Mahalliy pul ishlash modeli.** Raqiblarning boshlang'ich narxi $8–$15/oy. O'zbekiston uchun bu
   qimmat va xorijiy karta talab qiladi. Payme/Click orqali arzon kredit paketlari eng katta bo'shliq.
2. **Marketing yordamchisi.** Higgsfield daromadining asosiy manbai marketing kontenti. Bizning
   `/marketing` sahifamiz (9:16, 1:1 reklama) shu segmentga to'g'ri keladi. Uni asosiy funksiyaga
   aylantirish kerak.
3. **Xavfsiz ochiq kod.** Eng yaqin OSS raqib "senzurasiz" va yopiq API'ga bog'langan. Aurevid
   litsenziyasi aniq modellar, moderatsiya va o'z serverida to'liq ishlash bilan farqlanadi.
4. **Telegram.** O'zbekistonda asosiy kanal Telegram. Telegram bot (rejada) tarqatish uchun muhim.
5. **B2B.** Higgsfield B2B daromadini 10 barobar oshirgan. Mahalliy agentliklar va do'konlar uchun
   "jamoa" tarifi keyingi qadam bo'lishi mumkin.

## 8. Topilmagan ma'lumotlar (qo'lda tekshirish kerak)

- **O'zbekistondagi mahalliy raqiblar** (Telegram botlar, mahalliy AI studiyalar) avtomatik qidiruvda
  topilmadi. Telegram'da qo'lda qidirish kerak.
- Higgsfield tariflarining aniq narxlari (sahifa JavaScript bilan yuklanadi).
- Leonardo, Krea, PixVerse, Vidu, Hailuo ilovasi bo'yicha daromad va foydalanuvchi raqamlari.
- Raqiblarda o'zbek tili bormi yoki yo'qmi (har birida qo'lda tekshirish kerak).
- O'zbekiston bozori hajmi: AI rasm/video uchun to'lashga tayyor biznes va yaratuvchilar soni.

## Manbalar

Hammasi 2026-11-19 da o'qilgan.

- Sacra: [Higgsfield](https://sacra.com/c/higgsfield/), [Runway](https://sacra.com/c/runway/),
  [Midjourney](https://sacra.com/c/midjourney/), [Kling](https://sacra.com/c/kling/),
  [OpenArt](https://sacra.com/c/openart/), [Pika](https://sacra.com/c/pika/),
  [Luma AI](https://sacra.com/c/luma-ai/), [MiniMax](https://sacra.com/c/minimax/),
  [Black Forest Labs](https://sacra.com/c/black-forest-labs/), [Stability AI](https://sacra.com/c/stability-ai/),
  [Synthesia](https://sacra.com/c/synthesia/), [HeyGen](https://sacra.com/c/heygen/),
  [ComfyUI](https://sacra.com/c/comfyui/)
- Wikipedia: [Higgsfield AI (ru)](https://ru.wikipedia.org/wiki/Higgsfield_AI),
  [Runway](https://en.wikipedia.org/wiki/Runway_(company)), [Kuaishou](https://en.wikipedia.org/wiki/Kuaishou),
  [Kling AI](https://en.wikipedia.org/wiki/Kling_AI), [Ideogram](https://en.wikipedia.org/wiki/Ideogram_(text-to-image_model)),
  [Magnific (Freepik)](https://en.wikipedia.org/wiki/Freepik), [Canva](https://en.wikipedia.org/wiki/Canva),
  [Lightricks](https://en.wikipedia.org/wiki/Lightricks), [Synthesia](https://en.wikipedia.org/wiki/Synthesia_(company)),
  [Sora](https://en.wikipedia.org/wiki/Sora_(text-to-video_model)), [MiniMax](https://en.wikipedia.org/wiki/MiniMax_(company)),
  [Stability AI](https://en.wikipedia.org/wiki/Stability_AI), [Dream Machine](https://en.wikipedia.org/wiki/Dream_Machine_(text-to-video_model))
- Rasmiy sahifalar: [Higgsfield pricing](https://higgsfield.ai/pricing)
- Vercel shablonlari: [alt text](https://vercel.com/templates/next.js/ai-alt-text-generator),
  [AI SDK image](https://vercel.com/templates/next.js/ai-sdk-image-generator),
  [Scribble Diffusion](https://vercel.com/templates/next.js/scribble-diffusion),
  [fal image](https://vercel.com/templates/next.js/fal-image-generator),
  [Gemini image](https://vercel.com/templates/next.js/gemini-2-0-flash-image-generation-and-editing),
  [Tersa](https://vercel.com/templates/next.js/tersa-ai-workflow-canvas),
  [Vectr](https://vercel.com/templates/next.js/natural-language-image-search),
  [semantic search](https://vercel.com/templates/next.js/semantic-image-search),
  [fal video](https://vercel.com/templates/next.js/fal-video-generator),
  [live transcription](https://vercel.com/templates/next.js/nextjslive-transcription),
  [Mux AI workflows](https://vercel.com/templates/next.js/mux-ai-vercel-workflows-starter)
- GitHub API (yulduzlar, litsenziyalar): ComfyUI, AUTOMATIC1111, Fooocus, InvokeAI, SwarmUI,
  [Open-Generative-AI](https://github.com/Anil-matcha/Open-Generative-AI), Wan2.2, HunyuanVideo,
  LTX-Video, Open-Sora, Pollinations, WanGP, Open WebUI, vercel-labs/tersa, vercel-labs/vectr,
  vercel-labs/ai-sdk-image-generator, vercel-labs/semantic-image-search, muxinc/nextjs-video-ai-workflows,
  fal-ai-community/video-generator-demo, deepgram-starters/nextjs-live-transcription,
  google-gemini/gemini-image-editing-nextjs-quickstart
