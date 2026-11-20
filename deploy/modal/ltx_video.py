# SPDX-License-Identifier: AGPL-3.0-or-later
"""LTX-2.3 text-to-video WITH audio on Modal, for Aurevid's `modal_video` provider (OPTIONAL, OFF).

NOT TESTED: written from the diffusers LTX-2 docs, never run (no GPU/Modal here). Check the first clip.

LICENCE: the weights are under the LTX-2 Community License Agreement (Lightricks, 2026-01-05), not
Apache-2.0: free only for entities with annual revenue below USD 10M, a paid commercial licence above it;
the Gemma text encoder keeps Google's terms. Aurevid therefore hides the `ltx-2.3` model (commercial_use
"unclear") unless the owner records an exception in MODEL_LICENSES.md. Read that file before deploying.

Deploy (same flow as wan_video.py, see README.uz.md):
    modal run deploy/modal/ltx_video.py::download     # once: fetches the weights (tens of GB) into a volume
    modal deploy deploy/modal/ltx_video.py

Two web endpoints behind Modal's proxy auth (headers `Modal-Key` / `Modal-Secret`), no secret in this file:
    POST .../submit  {model, prompt, width, height, frames, seed}  ->  {"call_id": "..."}
    GET  .../result?call_id=...                                    ->  202 while running, else the mp4
The mp4 has an AAC audio track. `model` must be "ltx-2.3" (422 otherwise), so a Wan URL pasted by mistake
or the other way round fails loudly instead of making the wrong clip.
"""

import modal

MODEL = "ltx-2.3"  # the id Aurevid sends
BASE_REPO = "diffusers/LTX-2.3-Diffusers"  # pipeline layout (transformer, Gemma encoder, VAEs, vocoder)
LORA_REPO = "Lightricks/LTX-2.3"
# Distilled LoRA on top of the base pipeline: 8 steps and no CFG instead of 30 steps with 3-4 guidance
# passes, i.e. several times less GPU time per clip. (Name checked on the HF file list 2026-11-21.)
LORA_FILE = "ltx-2.3-22b-distilled-lora-384-1.1.safetensors"
# VRAM: 22B DiT in bf16 is ~44 GB plus the Gemma 3 12B encoder (~24 GB) and activations; Lightricks says
# 32 GB+ with offloading. A100-80GB is the cheaper 80 GB card; use "H100" if clips are too slow
# (faster, higher price per second; which is cheaper per clip is not measured).
GPU = "A100-80GB"
FPS = 24

app = modal.App("aurevid-ltx")
cache = modal.Volume.from_name("aurevid-hf-cache", create_if_missing=True)

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "diffusers",  # needs a release with LTX2Pipeline (LTX-2.3 support)
        "transformers",
        "accelerate",
        "sentencepiece",
        "peft",
        "av",
        "huggingface_hub",
    )
    .env({"HF_HOME": "/cache"})
)
web_image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi[standard]")


@app.function(image=gpu_image, volumes={"/cache": cache}, timeout=7200)
def download():
    """Fetches the weights once, so the first video does not wait for them."""
    from huggingface_hub import hf_hub_download, snapshot_download

    snapshot_download(BASE_REPO)
    hf_hub_download(LORA_REPO, LORA_FILE)
    cache.commit()


# Idle GPU time is billed: a short scale-down window (same as Wan). Loading 22B weights makes a cold
# start slow, so the first clip after a pause waits longer than on Wan; cost per clip: not measured.
@app.cls(
    image=gpu_image,
    gpu=GPU,
    volumes={"/cache": cache},
    timeout=3600,
    scaledown_window=30,
    memory=65536,
)
class Ltx:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import LTX2Pipeline

        self.pipe = LTX2Pipeline.from_pretrained(BASE_REPO, dtype=torch.bfloat16)
        self.pipe.load_lora_weights(LORA_REPO, weight_name=LORA_FILE, adapter_name="distilled")
        self.pipe.set_adapters("distilled", 1.0)
        self.pipe.enable_model_cpu_offload()  # keeps peak VRAM well below 80 GB
        self.pipe.vae.enable_tiling()

    @modal.method()
    def generate(self, prompt: str, width: int, height: int, frames: int, seed: int) -> bytes:
        import tempfile

        import torch
        from diffusers.pipelines.ltx2.utils import DISTILLED_SIGMA_VALUES
        from diffusers.utils import encode_video

        video, audio = self.pipe(
            prompt=prompt,
            width=width,
            height=height,
            num_frames=frames,
            frame_rate=float(FPS),
            num_inference_steps=8,  # as in the diffusers distilled example
            sigmas=DISTILLED_SIGMA_VALUES,
            guidance_scale=1.0,  # distilled: no classifier-free guidance
            generator=torch.Generator("cuda").manual_seed(seed),
            output_type="np",
            return_dict=False,
        )
        with tempfile.NamedTemporaryFile(suffix=".mp4") as handle:
            encode_video(
                video[0],
                fps=FPS,
                audio=audio[0].float().cpu(),
                audio_sample_rate=self.pipe.vocoder.config.output_sampling_rate,
                output_path=handle.name,
            )
            return open(handle.name, "rb").read()


@app.function(image=web_image)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def submit(item: dict):
    from fastapi import HTTPException

    prompt = str(item.get("prompt", ""))[:1000]
    width, height, frames = int(item["width"]), int(item["height"]), int(item["frames"])
    # LTX-2: sizes in multiples of 32, and 8k+1 frames (121 is five seconds at 24 fps)
    bad_size = width % 32 or height % 32 or (frames - 1) % 8 or not 9 <= frames <= 121
    if item.get("model") != MODEL or not prompt or bad_size:
        raise HTTPException(status_code=422)
    call = Ltx().generate.spawn(prompt, width, height, frames, int(item.get("seed", 0)))
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
