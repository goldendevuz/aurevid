# O'z Modal hisobingizda bepul video (qo'llanma)

Aurevid har bir foydalanuvchiga loyiha kalitidan 2 ta bepul video beradi. Ko'proq kerak bo'lsa, o'z
**Modal** hisobingizni ulang: Modal har oy bepul kredit beradi (hozir $30, aniq miqdorni
modal.com/pricing sahifasida tekshiring). Bu taxminan oyiga 150–300 ta qisqa klip. Pul faqat klip
tayyorlanayotgan paytdagi GPU vaqti uchun hisoblanadi.

Sizga kerak: kompyuter (Windows, macOS yoki Linux), Python 3.10+ va 15–20 daqiqa vaqt.

1. **Hisob oching:** <https://modal.com> saytida GitHub yoki Google orqali ro'yxatdan o'ting.
2. **Modal dasturini o'rnating** (terminalda):
   ```bash
   pip install modal
   modal setup
   ```
   `modal setup` brauzerni ochadi, hisobingizga kirishni tasdiqlang.
3. **Aurevid kodini yuklab oling:**
   ```bash
   git clone https://github.com/goldendevuz/aurevid.git
   cd aurevid
   ```
4. **Modelni bir marta yuklang** (~20 GB, bir necha daqiqa):
   ```bash
   modal run deploy/modal/wan_video.py::download
   ```
5. **Ishga tushiring:**
   ```bash
   modal deploy deploy/modal/wan_video.py
   ```
   Oxirida ikkita manzil chiqadi. Sizga `…-submit…modal.run` bilan tugaydigan manzil kerak.
6. **Token yarating:** <https://modal.com/settings/proxy-auth-tokens> sahifasida yangi token
   yarating. Sizga **Token ID** (`wk-…`) va **Token Secret** (`ws-…`) beriladi.
7. **Aurevid'ga ulang:** Sozlamalar → **Modal** bo'limiga submit manzilini, Token ID va Token
   Secret'ni kiriting. Kalitlar serverda shifrlangan holda saqlanadi va hech kimga ko'rsatilmaydi.
8. **Ishlating:** Studio → Video → **Wan 2.2 TI2V-5B (Modal)**.

**Maslahatlar**
- Tokenni hech kimga yubormang va chatlarga yozmang. Shubha bo'lsa, Modal'da o'chirib yangisini yarating.
- Modal → Settings → Usage & Billing bo'limida **xarajat chegarasini** bepul kredit miqdoriga
  qo'ying, shunda kartangizdan pul yechilmaydi.
- GPU uzoq turib qolgan bo'lsa, birinchi klip uni ishga tushirish uchun biroz ko'proq kutadi.
