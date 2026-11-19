# SPDX-License-Identifier: AGPL-3.0-or-later
"""MMAudio video-to-audio on Modal, for Aurevid's post-processing pipeline.

Deploy (see README.md next to this file):
    modal run deploy/modal/mmaudio_v2a.py::download     # once: fetches the weights into a volume
    modal deploy deploy/modal/mmaudio_v2a.py

One web endpoint, behind Modal's proxy auth:
    POST .../add-audio  multipart: video (mp4), prompt (str), seed (int)
                        -> the same mp4 with synchronised audio track
"""

import modal

MODEL_REPO = "hkchengrex/MMAudio"
VARIANT = "large_44k_v2"
GPU = "L40S"

app = modal.App("aurevid-mmaudio")
cache = modal.Volume.from_name("aurevid-mmaudio-cache", create_if_missing=True)

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "git")
    .pip_install(
        "torch",
        "torchaudio",
        "torchvision",
        "huggingface_hub",
        "mmaudio @ git+https://github.com/hkchengrex/MMAudio.git",
    )
    .env({"HF_HOME": "/cache"})
)
web_image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi[standard]")


@app.function(image=gpu_image, volumes={"/cache": cache}, timeout=3600)
def download():
    """Fetches MMAudio weights once (~7 GB total for large_44k_v2 + externals)."""
    from mmaudio.eval_utils import all_model_cfg

    cfg = all_model_cfg[VARIANT]
    cfg.download_if_needed()
    cache.commit()


@app.cls(image=gpu_image, gpu=GPU, volumes={"/cache": cache}, timeout=600, scaledown_window=120)
class AudioGen:
    @modal.enter()
    def load(self):
        import torch
        from mmaudio.eval_utils import ModelConfig, all_model_cfg
        from mmaudio.model.flow_matching import FlowMatching
        from mmaudio.model.networks import get_my_mmaudio
        from mmaudio.model.utils.features_utils import FeaturesUtils

        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

        self.device = "cuda"
        self.dtype = torch.bfloat16

        model_cfg: ModelConfig = all_model_cfg[VARIANT]
        model_cfg.download_if_needed()
        self.seq_cfg = model_cfg.seq_cfg

        self.feature_utils = FeaturesUtils(model_cfg=model_cfg, device=self.device)

        self.net = get_my_mmaudio(model_cfg.model_name).to(self.device, self.dtype)
        self.net.load_state_dict(
            torch.load(model_cfg.model_path, map_location="cpu")["model"]
        )
        self.net.eval()
        self.net.update_seq_lengths(
            self.seq_cfg.latent_seq_len,
            self.seq_cfg.clip_seq_len,
            self.seq_cfg.sync_seq_len,
        )

    @modal.method()
    def generate(self, video_bytes: bytes, prompt: str, seed: int) -> bytes:
        """Accept silent mp4, return mp4 with generated audio track."""
        import tempfile

        import torch
        import torchaudio
        from mmaudio.eval_utils import generate, load_video, make_video
        from mmaudio.model.flow_matching import FlowMatching

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
            vf.write(video_bytes)
            video_path = vf.name

        # Load video frames for CLIP and Synchformer
        duration = self.seq_cfg.duration
        clip_frames, sync_frames, _ = load_video(video_path, duration)

        rng = torch.Generator(device=self.device)
        if seed >= 0:
            rng.manual_seed(seed)
        else:
            rng.seed()

        fm = FlowMatching(min_sigma=0, inference_mode="euler", num_steps=25)

        with torch.inference_mode():
            audios = generate(
                clip_frames=clip_frames,
                sync_frames=sync_frames,
                text_prompts=[prompt],
                negative_text=["speech, low quality, distortion"],
                feature_utils=self.feature_utils,
                net=self.net,
                fm=fm,
                rng=rng,
                cfg_strength=4.5,
            )

        audio = audios.float().cpu()[0]

        with tempfile.NamedTemporaryFile(suffix=".flac", delete=False) as af:
            torchaudio.save(af.name, audio, self.seq_cfg.sampling_rate)
            audio_path = af.name

        # Mux: combine original video with generated audio
        import subprocess

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as out:
            output_path = out.name

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return open(output_path, "rb").read()


@app.function(image=web_image)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
async def add_audio(request: "starlette.requests.Request"):
    """Multipart: file=video.mp4, prompt=str, seed=int. Returns mp4 with audio."""
    import starlette.requests
    from fastapi import HTTPException, Response

    form = await request.form()
    video_file = form.get("file")
    prompt = str(form.get("prompt", ""))[:500]
    seed = int(form.get("seed", 0))

    if not video_file:
        raise HTTPException(status_code=422, detail="Missing video file")

    video_bytes = await video_file.read()
    if len(video_bytes) < 1000:
        raise HTTPException(status_code=422, detail="Video too small")

    call = AudioGen().generate.spawn(video_bytes, prompt, seed)
    return {"call_id": call.object_id}


@app.function(image=web_image)
@modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
def audio_result(call_id: str):
    from fastapi import Response

    try:
        data = modal.FunctionCall.from_id(call_id).get(timeout=0)
    except TimeoutError:
        return Response(status_code=202)
    return Response(content=data, media_type="video/mp4")
