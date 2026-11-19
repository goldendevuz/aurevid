# Your own video GPU on Modal

Runs Wan 2.2 (Apache-2.0 weights) on a GPU in **your** Modal workspace. Modal's Starter plan gives monthly free credit
(check modal.com/pricing); a GPU is billed only while a clip is being made.

```bash
pip install modal
modal setup                                          # sign in once, in the browser
modal run deploy/modal/wan_video.py::download        # once: fetches the weights (about 20 GB) into a volume
modal deploy deploy/modal/wan_video.py               # prints the two endpoint URLs
```

O'zbekcha qo'llanma: [README.uz.md](README.uz.md).

1. Create a **proxy auth token** at <https://modal.com/settings/proxy-auth-tokens> (you get a key id and a secret).
2. In Aurevid, Settings, provider **Modal**: paste the URL of the `…-submit` endpoint, the token id and the token secret.
3. In Studio choose Video, then **Wan 2.2 TI2V-5B (your Modal)**.

The first clip after the GPU has been idle waits for it to start. Watch your balance in the Modal dashboard.
