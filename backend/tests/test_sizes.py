# SPDX-License-Identifier: AGPL-3.0-or-later
"""Honest sizes: jobs and assets store the real output resolution, never the requested label."""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.config import get_settings
from app.images import probe_mp4_size, store_video, store_video_file
from app.providers import modal_video as mv
from app.providers.base import fit_long_side, output_dimensions
from app.providers.cloudflare import KLEIN, SCHNELL, CloudflareProvider
from app.providers.registry import get_provider
from app.worker import run_once
from tests.conftest import csrf_headers

DEMO_MP4 = Path(__file__).resolve().parent.parent / "app" / "providers" / "media" / "demo.mp4"
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def _clip(path: Path, size: str, audio: bool = False) -> bytes:
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=blue:s={size}:d=0.5:r=24"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc", "-c:a", "aac", "-shortest"]
    cmd += ["-pix_fmt", "yuv420p", "-c:v", "libx264", str(path)]
    subprocess.run(cmd, check=True)  # noqa: S603
    return path.read_bytes()


@needs_ffmpeg
@pytest.mark.parametrize("size,audio", [("864x496", False), ("1920x1080", True), ("480x854", True)])
def test_probe_reads_the_files_own_size(tmp_path, size, audio):
    data = _clip(tmp_path / "c.mp4", size, audio)
    w, h = (int(x) for x in size.split("x"))
    assert probe_mp4_size(data) == (w, h) == probe_mp4_size(tmp_path / "c.mp4")


def test_probe_demo_clip_and_garbage():
    assert probe_mp4_size(DEMO_MP4) == (320, 320)
    assert probe_mp4_size(b"not an mp4 at all, really not") is None
    assert probe_mp4_size(Path("/nonexistent/file.mp4")) is None


@needs_ffmpeg
def test_stored_video_gets_the_real_size_not_the_declared_one(tmp_path):
    data = _clip(tmp_path / "c.mp4", "864x496")
    assert (store_video(data, 1344, 768).width, store_video(data, 1344, 768).height) == (864, 496)
    part = tmp_path / "p.mp4"
    part.write_bytes(data)
    stored = store_video_file(part, 1344, 768)
    assert (stored.width, stored.height) == (864, 496)


def test_output_dimensions_follow_the_model_not_the_size_label():
    modal = get_provider("modal_video")
    wan = modal.model(mv.WAN)
    for size in ("small", "medium", "large"):  # the label changes nothing: 480p-class always
        assert output_dimensions(wan, "16:9", size) == (832, 480)
    assert output_dimensions(wan, "9:16", "large") == (480, 832)
    cf = CloudflareProvider.info
    schnell = next(m for m in cf.models if m.id == SCHNELL)
    klein = next(m for m in cf.models if m.id == KLEIN)
    assert output_dimensions(schnell, "1:1", "small") == (1024, 1024)  # fixed by the endpoint
    assert output_dimensions(klein, "1:1", "small") == (512, 512)  # klein follows the size
    assert output_dimensions(klein, "16:9", "large") == (1344, 768)


def test_fit_long_side_keeps_the_ratio_on_the_64_grid():
    assert fit_long_side("16:9", 1920) == (1920, 1088)
    assert fit_long_side("9:16", 1920) == (1088, 1920)
    assert fit_long_side("1:1", 1920) == (1920, 1920)
    for aspect in ("4:3", "3:4"):
        w, h = fit_long_side(aspect, 1920)
        assert max(w, h) == 1920 and w % 64 == 0 and h % 64 == 0


def _owner_modal():
    s = get_settings()
    s.modal_submit_url = "https://owner--aurevid-wan-submit.modal.run"
    s.modal_token_id, s.modal_token_secret = "wk", "ws"
    s.signup_credits = 100


async def test_modal_job_reports_480p_even_when_large_is_chosen(alice):
    _owner_modal()
    body = {
        "prompt": "waves on a calm beach",
        "provider": "modal_video",
        "model": mv.WAN,
        "aspect_ratio": "16:9",
        "size": "large",
    }
    r = await alice.post("/api/jobs", json=body, headers=csrf_headers(alice))
    assert r.status_code == 201, r.text
    params = r.json()["params"]
    assert (params["width"], params["height"]) == (832, 480)  # not the 1344x768 of "large"
    assert params["size"] == "large"  # what was asked, kept for Remix
    # The catalog tells the UI the same thing.
    modal = next(p for p in (await alice.get("/api/providers")).json() if p["id"] == "modal_video")
    wan = next(m for m in modal["models"] if m["id"] == mv.WAN)
    assert wan["fixed_dimensions"]["16:9"] == [832, 480]


async def test_finished_job_params_match_the_file(alice, monkeypatch):
    _owner_modal()

    async def fake_generate(self, req, creds):
        from app.providers.base import GeneratedMedia

        return GeneratedMedia(DEMO_MP4.read_bytes(), "video/mp4")

    monkeypatch.setattr(mv.ModalVideoProvider, "generate", fake_generate)
    body = {"prompt": "waves on a calm beach", "provider": "modal_video", "model": mv.WAN}
    job = (
        await alice.post(
            "/api/jobs", json={**body, "aspect_ratio": "16:9"}, headers=csrf_headers(alice)
        )
    ).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    asset = done["assets"][0]
    assert (asset["width"], asset["height"]) == (320, 320)  # the demo file's real size
    assert (done["params"]["width"], done["params"]["height"]) == (asset["width"], asset["height"])
    # The request still asked the provider for its native 832x480.
    assert (done["params"]["gen_width"], done["params"]["gen_height"]) == (832, 480)


async def test_image_job_params_match_the_decoded_file(alice):
    job = (
        await alice.post(
            "/api/jobs",
            json={
                "provider": "demo",
                "model": "gradient",
                "prompt": "a red apple",
                "size": "large",
            },
            headers=csrf_headers(alice),
        )
    ).json()
    await run_once()
    done = (await alice.get(f"/api/jobs/{job['id']}")).json()
    asset = done["assets"][0]
    # The demo model draws a quarter-size picture: the stored numbers say so.
    assert (asset["width"], asset["height"]) == (256, 256)
    assert (done["params"]["width"], done["params"]["height"]) == (256, 256)


async def test_cloudflare_schnell_job_reports_1024_whatever_the_size_label(alice):
    s = get_settings()
    s.cf_account_id, s.cf_api_token = "a" * 32, "tok"
    r = await alice.post(
        "/api/jobs",
        json={"provider": "cloudflare", "model": SCHNELL, "prompt": "a red apple", "size": "small"},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 201, r.text
    assert (r.json()["params"]["width"], r.json()["params"]["height"]) == (1024, 1024)
