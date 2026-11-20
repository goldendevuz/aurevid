# SPDX-License-Identifier: AGPL-3.0-or-later
"""Aurevid GPU worker: makes videos for an Aurevid server on this machine's NVIDIA GPU.

Loop: claim a job (POST /api/gpu-worker/claim) -> generate with Wan 2.2 TI2V-5B (Apache-2.0,
diffusers) -> upload the mp4 (POST /api/gpu-worker/{id}/complete) or report a failure.
Only outbound HTTPS is used; no port is opened on this machine.

Environment:
    AUREVID_URL        base URL of the server, e.g. https://aurevid.example (required)
    GPU_WORKER_TOKEN   the same value as GPU_WORKER_TOKEN in the server's .env (required)
    POLL_SECONDS       wait between claims when the queue is empty (default 10)
    STEPS              diffusion steps (default 20; more = slower, slightly better)
"""

import contextlib
import logging
import os
import signal
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

MODEL_ID = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
NEGATIVE_PROMPT = "blurry, low quality, distorted, watermark, text, subtitles, static image"
MAX_BACKOFF = 300.0
UPLOAD_TRIES = 4

log = logging.getLogger("aurevid-gpu-worker")
_stop = False


class Misconfigured(Exception):
    """The server refuses this worker for good (wrong token): retrying cannot help."""


def _request_stop(signum, _frame) -> None:
    global _stop
    log.info("signal %s: finishing the current job, then stopping", signum)
    _stop = True


def _sleep(seconds: float) -> None:
    """Sleep in short steps so Ctrl+C / docker stop is honoured quickly."""
    end = time.monotonic() + seconds
    while not _stop and time.monotonic() < end:
        time.sleep(min(1.0, end - time.monotonic()))


class Generator:
    """Loads Wan 2.2 once and keeps it on the GPU."""

    def __init__(self, steps: int) -> None:
        import torch
        from diffusers import AutoencoderKLWan, WanPipeline

        if not torch.cuda.is_available():
            raise SystemExit("No CUDA GPU found. Run with `docker run --gpus all ...`.")
        self.torch, self.steps = torch, steps
        log.info("loading %s (the first start downloads about 20 GB)", MODEL_ID)
        vae = AutoencoderKLWan.from_pretrained(MODEL_ID, subfolder="vae", torch_dtype=torch.float32)
        self.t2v = WanPipeline.from_pretrained(MODEL_ID, vae=vae, torch_dtype=torch.bfloat16)
        self.t2v.to("cuda")
        self._i2v = None
        log.info("model ready on %s", torch.cuda.get_device_name(0))

    def _image_pipe(self):
        if self._i2v is None:
            from diffusers import WanImageToVideoPipeline

            self._i2v = WanImageToVideoPipeline.from_pipe(self.t2v)  # shares the loaded weights
        return self._i2v

    def run(self, job: dict, image_path: Path | None, out_path: Path) -> None:
        from diffusers.utils import export_to_video, load_image

        torch = self.torch
        args = {
            "prompt": job["prompt"],
            "negative_prompt": NEGATIVE_PROMPT,
            "height": int(job["height"]),
            "width": int(job["width"]),
            "num_frames": int(job["frames"]),
            "guidance_scale": 5.0,
            "num_inference_steps": self.steps,
            "generator": torch.Generator("cuda").manual_seed(int(job["seed"])),
        }
        pipe = self.t2v
        if image_path is not None:
            pipe = self._image_pipe()
            args["image"] = load_image(str(image_path))
        try:
            frames = pipe(**args).frames[0]
            export_to_video(frames, str(out_path), fps=int(job.get("fps", 24)))
        finally:
            torch.cuda.empty_cache()


def api(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    resp = client.request(method, path, **kwargs)
    if resp.status_code == 401:
        raise Misconfigured("The server rejected GPU_WORKER_TOKEN (401). Check both .env files.")
    return resp


def download_image(client: httpx.Client, base: str, url: str, dest: Path) -> None:
    # Only ever fetch from the server we were configured with.
    full = urljoin(base, url)
    if urlsplit(full).netloc != urlsplit(base).netloc:
        raise ValueError("image url points to another host")
    resp = api(client, "GET", full)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def upload(client: httpx.Client, job_id: str, path: Path) -> None:
    """Retries network trouble; if it never works the lease expires and the job is retried."""
    for attempt in range(1, UPLOAD_TRIES + 1):
        try:
            with path.open("rb") as handle:
                resp = api(
                    client,
                    "POST",
                    f"/api/gpu-worker/{job_id}/complete",
                    files={"file": ("video.mp4", handle, "video/mp4")},
                )
        except httpx.HTTPError as exc:
            log.warning("upload attempt %d failed: %s", attempt, type(exc).__name__)
        else:
            if resp.status_code == 201:
                log.info("job %s uploaded", job_id)
                return
            if resp.status_code in (404, 409, 413, 415):  # final answers: do not retry
                log.error("job %s upload refused (%d)", job_id, resp.status_code)
                return
            log.warning("upload attempt %d got HTTP %d", attempt, resp.status_code)
        _sleep(min(MAX_BACKOFF, 5.0 * 2**attempt))
    log.error("job %s: giving up on the upload, the lease will expire", job_id)


def report_failure(client: httpx.Client, job_id: str, message: str) -> None:
    try:
        api(client, "POST", f"/api/gpu-worker/{job_id}/fail", json={"message": message[:500]})
    except httpx.HTTPError:
        log.warning("could not report the failure; the lease will expire instead")


def handle_job(client: httpx.Client, gen: Generator, base: str, job: dict) -> None:
    job_id = job["job_id"]
    log.info("job %s: %sx%s, %s frames", job_id, job["width"], job["height"], job["frames"])
    with tempfile.TemporaryDirectory(prefix="aurevid-") as tmp:
        out = Path(tmp) / "out.mp4"
        image = Path(tmp) / "start.jpg" if job.get("image_url") else None
        started = time.monotonic()
        try:
            if image is not None:
                download_image(client, base, job["image_url"], image)
            gen.run(job, image, out)
        except Misconfigured:
            raise
        except Exception as exc:  # noqa: BLE001 - any generation error must reach the server
            log.exception("job %s failed", job_id)
            report_failure(client, job_id, f"{type(exc).__name__}: {exc}")
            return
        log.info("job %s generated in %.0f s", job_id, time.monotonic() - started)
        upload(client, job_id, out)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    base = os.environ.get("AUREVID_URL", "").strip().rstrip("/")
    token = os.environ.get("GPU_WORKER_TOKEN", "").strip()
    if not base or not token:
        log.error("Set AUREVID_URL and GPU_WORKER_TOKEN")
        return 2
    host = urlsplit(base).hostname or ""
    if not base.startswith("https://") and host not in ("localhost", "127.0.0.1"):
        log.error("AUREVID_URL must be https:// (the token would travel in clear text)")
        return 2
    poll = float(os.environ.get("POLL_SECONDS", "10"))
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    client = httpx.Client(
        base_url=base,
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(60.0, read=600.0),
        follow_redirects=False,
    )
    gen = Generator(int(os.environ.get("STEPS", "20")))
    backoff = poll
    log.info("worker started, server %s", base)
    with contextlib.closing(client):
        while not _stop:
            try:
                resp = api(client, "POST", "/api/gpu-worker/claim")
                if resp.status_code == 200:
                    backoff = poll
                    handle_job(client, gen, base, resp.json())
                    continue
                if resp.status_code != 204:
                    raise httpx.HTTPStatusError("claim", request=resp.request, response=resp)
                backoff = poll
            except Misconfigured as exc:
                log.error("%s", exc)
                return 1
            except (httpx.HTTPError, ValueError) as exc:
                backoff = min(MAX_BACKOFF, backoff * 2)
                log.warning("claim failed (%s); retry in %.0f s", type(exc).__name__, backoff)
            _sleep(backoff)
    log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
