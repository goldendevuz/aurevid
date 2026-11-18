# SPDX-License-Identifier: AGPL-3.0-or-later
"""Wan 2.2 text-to-video on Modal, for Aurevid's `modal_video` provider.

Deploy (see README.md next to this file):
    modal run deploy/modal/wan_video.py::download     # once: fetches the weights (~20 GB) into a volume
    modal deploy deploy/modal/wan_video.py

Two web endpoints, both behind Modal's proxy auth (headers `Modal-Key` and `Modal-Secret` of a proxy auth token
made in the workspace settings), so there is no secret in this file:
    POST .../submit  {prompt, width, height, frames, seed}  ->  {"call_id": "..."}
    GET  .../result?call_id=...                             ->  202 while running, else the mp4

Videos take minutes, so the work is spawned and polled instead of held on one HTTP request.
"""

import modal

MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"  # Apache-2.0 weights
GPU = "L40S"
STEPS = 30
FPS = 24

app = modal.App("aurevid-wan")
cache = modal.Volume.from_name("aurevid-hf-cache", create_if_missing=True)

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "diffusers",
        "transformers",
        "accelerate",
        "sentencepiece",
        "ftfy",
        "imageio",
        "imageio-ffmpeg",
        "huggingface_hub",
    )
    .env({"HF_HOME": "/cache"})
)
web_image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi[standard]")


@app.function(image=gpu_image, volumes={"/cache": cache}, timeout=3600)
def download():
    """Fetches the weights once, so the first video does not wait for them."""
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_ID)
    cache.commit()


@app.cls(image=gpu_image, gpu=GPU, volumes={"/cache": cache}, timeout=1800, scaledown_window=120)
class Wan:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import AutoencoderKLWan, WanPipeline

        vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
        self.pipe = WanPipeline.from_pretrained(MODEL_ID, vae=vae, torch_dtype=torch.bfloat16)
        self.pipe.to("cuda")

    @modal.method()
    def generate(self, prompt: str, width: int, height: int, frames: int, seed: int) -> bytes:
        import tempfile

        import torch
        from diffusers.utils import export_to_video

        out = self.pipe(
            prompt=prompt,
            height=height,
            width=width,
            num_frames=frames,
            guidance_scale=5.0,
            num_inference_steps=STEPS,
            generator=torch.Generator("cuda").manual_seed(seed),
        ).frames[0]
        with tempfile.NamedTemporaryFile(suffix=".mp4") as handle:
            export_to_video(out, handle.name, fps=FPS)
            return open(handle.name, "rb").read()


@app.function(image=web_image)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def submit(item: dict):
    from fastapi import HTTPException

    prompt = str(item.get("prompt", ""))[:1000]
    width, height, frames = int(item["width"]), int(item["height"]), int(item["frames"])
    # Wan 2.2 5B: sizes in multiples of 32, and 4k+1 frames (121 is five seconds at 24 fps)
    if not prompt or width % 32 or height % 32 or (frames - 1) % 4 or not 5 <= frames <= 121:
        raise HTTPException(status_code=422)
    call = Wan().generate.spawn(prompt, width, height, frames, int(item.get("seed", 0)))
    return {"call_id": call.object_id}


@app.function(image=web_image)
@modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
def result(call_id: str):
    from fastapi import Response

    try:
        data = modal.FunctionCall.from_id(call_id).get(timeout=0)
    except TimeoutError:
        return Response(status_code=202)
    return Response(content=data, media_type="video/mp4")
