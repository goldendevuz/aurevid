# SPDX-License-Identifier: AGPL-3.0-or-later
"""Multi-scene video: all-or-nothing creation, ownership, joining, partial failure and retry."""

import asyncio
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from app import db
from app.config import get_settings
from app.images import asset_path
from app.models import Asset, CreditLedger, Job, ModerationEvent, Story, StoryStatus
from app.services import stitch, stories
from app.worker import run_once
from tests.conftest import csrf_headers

DEMO_MP4 = Path(__file__).resolve().parent.parent / "app" / "providers" / "media" / "demo.mp4"
HAVE_FFMPEG = stitch.available()
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg/ffprobe not installed")
BASE = {"provider": "demo", "model": "loop", "aspect_ratio": "16:9"}
SCENES = ["a lantern at dawn", "the lantern at noon", "the lantern at dusk"]


async def create(client, scenes=SCENES, **overrides):
    body = {**BASE, "scenes": scenes, **overrides}
    return await client.post("/api/stories", json=body, headers=csrf_headers(client))


async def run_all() -> None:
    while await run_once():
        pass


async def counts() -> tuple[int, int, int]:
    """(stories, jobs, ledger rows)"""
    out = []
    async with db.session_factory()() as s:
        for model in (Story, Job, CreditLedger):
            out.append((await s.execute(select(func.count()).select_from(model))).scalar_one())
    return tuple(out)


@pytest.fixture
def fake_join(monkeypatch):
    """Stand-in for ffmpeg (so the flow is tested even where it is not installed)."""
    calls = []

    async def concat(paths, out):
        calls.append(list(paths))
        out.write_bytes(DEMO_MP4.read_bytes())
        return stitch.ClipInfo("h264", 320, 320, "yuv420p", "24/1", False, duration=3 * len(paths))

    monkeypatch.setattr(stitch, "concat_clips", concat)
    return calls


async def final_assets(user_email_prefix: str | None = None) -> list[Asset]:
    async with db.session_factory()() as s:
        return list(
            (
                await s.execute(
                    select(Asset).where(Asset.job_id.is_(None), Asset.source == "generated")
                )
            )
            .scalars()
            .all()
        )


# --- creation ------------------------------------------------------------------------------


async def test_create_story_makes_one_job_per_scene_and_charges_each(alice, fake_join):
    r = await create(alice)
    assert r.status_code == 201, r.text
    story = r.json()
    assert story["status"] == "pending" and story["cost"] == 6 and story["final"] is None
    assert [s["index"] for s in story["scenes"]] == [0, 1, 2]
    assert [s["prompt"] for s in story["scenes"]] == SCENES
    for scene in story["scenes"]:
        job = scene["job"]
        assert job["kind"] == "video" and job["params"]["duration"] == 5
        assert job["story_id"] == story["id"] and job["status"] == "queued"
    assert (await alice.get("/api/credits")).json()["balance"] == 4


async def test_scene_count_is_2_to_4(alice):
    assert (await create(alice, scenes=["only one scene"])).status_code == 422
    assert (await create(alice, scenes=[f"scene number {i}" for i in range(5)])).status_code == 422
    assert (await create(alice, scenes=["ok scene", "  "])).status_code == 422
    assert await counts() == (0, 0, 1)  # just the signup grant


async def test_not_enough_credits_for_all_scenes_creates_and_charges_nothing(alice):
    async with db.session_factory()() as s:
        from app.models import User

        await s.execute(update(User).values(credit_balance=5))  # 3 scenes cost 6
        await s.commit()
    before = await counts()
    r = await create(alice)
    assert r.status_code == 402 and r.json()["detail"]["code"] == "insufficient_credits"
    assert await counts() == before
    assert (await alice.get("/api/credits")).json()["balance"] == 5


async def test_daily_limit_covers_all_scenes(alice):
    get_settings().daily_job_limit = 2
    before = await counts()
    r = await create(alice)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "daily_limit_reached"
    assert await counts() == before
    assert (await alice.get("/api/credits")).json()["balance"] == 10
    # Exactly the limit still works.
    assert (await create(alice, scenes=SCENES[:2])).status_code == 201


async def test_active_job_cap_is_not_bypassed(alice):
    # Default cap is 3 queued+running jobs per user: a 4-scene story must be refused whole.
    assert get_settings().max_active_jobs_per_user == 3
    before = await counts()
    r = await create(alice, scenes=[*SCENES, "the lantern at midnight"])
    assert r.status_code == 429 and r.json()["detail"]["code"] == "too_many_active_jobs"
    assert await counts() == before
    get_settings().max_active_jobs_per_user = 4  # an operator raising the cap enables 4 scenes
    async with db.session_factory()() as s:
        from app.models import User

        await s.execute(update(User).values(credit_balance=20))
        await s.commit()
    assert (await create(alice, scenes=[*SCENES, "the lantern at midnight"])).status_code == 201


async def test_moderation_rejects_whole_story(alice):
    before = (await counts())[:2]
    r = await create(alice, scenes=["a calm lake", "nude photo of a teenager"])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "prompt_rejected"
    assert (await counts())[:2] == before
    async with db.session_factory()() as s:  # category logged, prompt not stored
        assert (
            await s.execute(select(func.count()).select_from(ModerationEvent))
        ).scalar_one() == 1


async def test_unsupported_model_or_format_is_refused_whole(alice):
    assert (await create(alice, model="nope")).json()["detail"]["code"] == "unknown_model"
    r = await create(alice, aspect_ratio="4:3")
    assert r.json()["detail"]["code"] == "aspect_ratio_unsupported"
    r = await create(alice, model="gradient")  # an image model has no 5 s clips
    assert r.json()["detail"]["code"] == "duration_unsupported"
    assert (await counts())[:2] == (0, 0)
    assert (await alice.get("/api/credits")).json()["balance"] == 10


async def test_idempotency_key_returns_the_same_story(alice):
    headers = {**csrf_headers(alice), "Idempotency-Key": "k-123"}
    body = {**BASE, "scenes": SCENES[:2]}
    a = await alice.post("/api/stories", json=body, headers=headers)
    b = await alice.post("/api/stories", json=body, headers=headers)
    assert a.status_code == b.status_code == 201 and a.json()["id"] == b.json()["id"]
    assert (await alice.get("/api/credits")).json()["balance"] == 6  # charged once


# --- ownership -----------------------------------------------------------------------------


async def test_other_users_cannot_see_or_touch_a_story(alice, bob, fake_join):
    sid = (await create(alice)).json()["id"]
    assert (await bob.get(f"/api/stories/{sid}")).status_code == 404
    assert (await bob.get("/api/stories")).json() == []
    h = csrf_headers(bob)
    assert (await bob.post(f"/api/stories/{sid}/scenes/0/retry", headers=h)).status_code == 404
    assert (await bob.post(f"/api/stories/{sid}/stitch", headers=h)).status_code == 404
    assert (await bob.delete(f"/api/stories/{sid}", headers=h)).status_code == 404
    assert (await alice.get(f"/api/stories/{sid}")).status_code == 200
    assert len((await alice.get("/api/stories")).json()) == 1


async def test_scene_jobs_are_hidden_from_history_and_protected(alice, fake_join):
    story = (await create(alice)).json()
    assert (await alice.get("/api/jobs")).json() == []
    assert (await alice.get("/api/jobs/facets")).json()["total"] == 0
    await run_all()
    job_id = story["scenes"][0]["job"]["id"]
    r = await alice.delete(f"/api/jobs/{job_id}", headers=csrf_headers(alice))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "job_in_story"
    assert (await alice.get(f"/api/jobs/{job_id}")).status_code == 200


# --- joining -------------------------------------------------------------------------------


async def test_story_is_joined_when_every_scene_succeeded(alice, fake_join):
    sid = (await create(alice)).json()["id"]
    await run_once()
    await run_once()
    mid = (await alice.get(f"/api/stories/{sid}")).json()
    assert mid["status"] == "pending" and mid["final"] is None and not fake_join
    await run_once()
    done = (await alice.get(f"/api/stories/{sid}")).json()
    assert done["status"] == "ready" and done["error"] is None and done["finished_at"]
    assert len(fake_join) == 1 and len(fake_join[0]) == 3
    final = done["final"]
    assert final["mime"] == "video/mp4"
    f = await alice.get(final["url"])
    assert f.status_code == 200 and f.headers["content-type"] == "video/mp4"
    assert [s["job"]["status"] for s in done["scenes"]] == ["done"] * 3


async def test_joining_twice_creates_one_asset(alice, fake_join):
    sid = (await create(alice)).json()["id"]
    await run_all()
    await asyncio.gather(stories.settle(sid), stories.settle(sid), stories.settle(sid))
    await stories.settle(sid)
    assert len(await final_assets()) == 1
    assert len(fake_join) == 1


async def test_concurrent_joins_attach_one_video(alice, fake_join):
    sid = (await create(alice)).json()["id"]
    # All scenes finished but nobody has settled yet (finish hook skipped).
    async with db.session_factory()() as s:
        await s.execute(update(Job).values(status="done"))
        for job in (await s.execute(select(Job))).scalars():
            s.add(
                Asset(
                    user_id=job.user_id, job_id=job.id, source="generated", mime="video/mp4",
                    storage_key=f"{job.id}.mp4", width=320, height=320, size_bytes=1,
                )
            )  # fmt: skip
            asset_path(f"{job.id}.mp4").parent.mkdir(parents=True, exist_ok=True)
            asset_path(f"{job.id}.mp4").write_bytes(DEMO_MP4.read_bytes())
        await s.commit()
    await asyncio.gather(*(stories.settle(sid) for _ in range(4)))
    assert len(await final_assets()) == 1
    assert (await alice.get(f"/api/stories/{sid}")).json()["status"] == "ready"


async def test_stuck_stitching_is_recovered_by_the_janitor(alice, fake_join):
    sid = (await create(alice)).json()["id"]
    await run_all()
    async with db.session_factory()() as s:  # pretend the worker died mid-join
        await s.execute(
            update(Story).values(
                status=StoryStatus.stitching,
                final_asset_id=None,
                updated_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        for a in (await s.execute(select(Asset).where(Asset.job_id.is_(None)))).scalars():
            await s.delete(a)
        await s.commit()
    await stories.recover()
    assert (await alice.get(f"/api/stories/{sid}")).json()["status"] == "ready"
    assert len(await final_assets()) == 1


async def test_join_failure_is_safe_and_can_be_retried(alice, monkeypatch):
    async def boom(paths, out):
        raise stitch.StitchError()

    monkeypatch.setattr(stitch, "concat_clips", boom)
    sid = (await create(alice)).json()["id"]
    await run_all()
    failed = (await alice.get(f"/api/stories/{sid}")).json()
    assert failed["status"] == "failed" and failed["error"] == "stitch_failed"
    assert failed["final"] is None and "/" not in json.dumps(failed["error"])
    assert (await alice.get("/api/credits")).json()["balance"] == 4  # scenes stay charged

    async def fine(paths, out):
        out.write_bytes(DEMO_MP4.read_bytes())
        return stitch.ClipInfo("h264", 320, 320, "yuv420p", "24/1", False, duration=9)

    monkeypatch.setattr(stitch, "concat_clips", fine)
    r = await alice.post(f"/api/stories/{sid}/stitch", headers=csrf_headers(alice))
    assert r.status_code == 200, r.text
    await stories.settle(sid)  # (the endpoint also does this in the background)
    assert (await alice.get(f"/api/stories/{sid}")).json()["status"] == "ready"
    r = await alice.post(f"/api/stories/{sid}/stitch", headers=csrf_headers(alice))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "story_not_stitchable"


async def test_missing_ffmpeg_fails_the_story_without_leaking_anything(alice, monkeypatch):
    get_settings().ffmpeg_path = "definitely-not-installed-ffmpeg"
    monkeypatch.setattr(stitch, "ffprobe_bin", lambda: None)
    sid = (await create(alice)).json()["id"]
    await run_all()
    story = (await alice.get(f"/api/stories/{sid}")).json()
    assert story["status"] == "failed" and story["error"] == "stitch_failed"


# --- partial failure and retry -------------------------------------------------------------


async def test_failed_scene_leaves_a_partial_story_that_can_be_retried(alice, fake_join):
    scenes = [SCENES[0], "__fail__ broken scene", SCENES[2]]
    sid = (await create(alice, scenes=scenes)).json()["id"]
    await run_all()
    story = (await alice.get(f"/api/stories/{sid}")).json()
    assert story["status"] == "partial" and not fake_join
    assert [s["job"]["status"] for s in story["scenes"]] == ["done", "failed", "done"]
    assert (await alice.get("/api/credits")).json()["balance"] == 6  # failed scene refunded

    h = csrf_headers(alice)
    assert (await alice.post(f"/api/stories/{sid}/scenes/0/retry", headers=h)).status_code == 409
    assert (await alice.post(f"/api/stories/{sid}/scenes/3/retry", headers=h)).status_code == 404

    async with db.session_factory()() as s:  # the provider hiccup is over
        await s.execute(update(Job).where(Job.scene_index == 1).values(prompt="a working scene"))
        await s.commit()
    r = await alice.post(f"/api/stories/{sid}/scenes/1/retry", headers=h)
    assert r.status_code == 201, r.text
    retried = r.json()
    assert retried["status"] == "pending"
    assert retried["scenes"][1]["job"]["status"] == "queued" and retried["cost"] == 6
    assert (await alice.get("/api/credits")).json()["balance"] == 4  # charged like a new job
    # A second click while it runs is refused: the scene is not failed any more.
    assert (await alice.post(f"/api/stories/{sid}/scenes/1/retry", headers=h)).status_code == 409

    await run_all()
    done = (await alice.get(f"/api/stories/{sid}")).json()
    assert done["status"] == "ready" and done["final"] is not None
    assert len(fake_join) == 1 and len(await final_assets()) == 1
    async with db.session_factory()() as s:  # the failed try stays as history
        n = (
            await s.execute(select(func.count()).select_from(Job).where(Job.story_id == sid))
        ).scalar_one()
    assert n == 4


async def test_retry_is_refused_when_credits_are_short(alice, fake_join):
    scenes = [SCENES[0], "__fail__ broken scene"]
    sid = (await create(alice, scenes=scenes)).json()["id"]
    await run_all()
    async with db.session_factory()() as s:
        from app.models import User

        await s.execute(update(User).values(credit_balance=1))
        await s.commit()
    r = await alice.post(f"/api/stories/{sid}/scenes/1/retry", headers=csrf_headers(alice))
    assert r.status_code == 402
    assert (await alice.get("/api/credits")).json()["balance"] == 1
    assert (await alice.get(f"/api/stories/{sid}")).json()["status"] == "partial"


async def test_all_scenes_failing_marks_the_story_failed(alice, fake_join):
    sid = (await create(alice, scenes=["__fail__ one", "__fail__ two"])).json()["id"]
    await run_all()
    story = (await alice.get(f"/api/stories/{sid}")).json()
    assert story["status"] == "failed" and story["error"] is None
    assert (await alice.get("/api/credits")).json()["balance"] == 10  # everything refunded


# --- delete --------------------------------------------------------------------------------


async def test_delete_story_removes_clips_and_final_video(alice, fake_join):
    sid = (await create(alice)).json()["id"]
    h = csrf_headers(alice)
    assert (
        await alice.delete(f"/api/stories/{sid}", headers=h)
    ).status_code == 409  # still running
    await run_all()
    final_url = (await alice.get(f"/api/stories/{sid}")).json()["final"]["url"]
    assert (await alice.delete(f"/api/stories/{sid}", headers=h)).status_code == 204
    assert (await alice.get(f"/api/stories/{sid}")).status_code == 404
    assert (await alice.get(final_url)).status_code == 404
    async with db.session_factory()() as s:
        assert (await s.execute(select(func.count()).select_from(Asset))).scalar_one() == 0
        assert (await s.execute(select(func.count()).select_from(Job))).scalar_one() == 0


async def test_account_erasure_removes_stories(alice, fake_join):
    await create(alice)
    await run_all()
    r = await alice.request(
        "DELETE",
        "/api/me",
        json={"password": "correct horse battery"},
        headers=csrf_headers(alice),
    )
    assert r.status_code == 204, r.text
    async with db.session_factory()() as s:
        assert (await s.execute(select(func.count()).select_from(Story))).scalar_one() == 0


# --- ffmpeg: command construction (no ffmpeg needed) ---------------------------------------


def _clip(**kw) -> stitch.ClipInfo:
    base = dict(
        codec="h264", width=704, height=1280, pix_fmt="yuv420p", fps="24/1", has_audio=False
    )
    return stitch.ClipInfo(**{**base, **kw})


def test_copy_command_is_an_argument_list_without_shell_tricks():
    cmd = stitch.copy_command("ffmpeg", Path("/t/clips.txt"), Path("/t/out.mp4"))
    assert cmd[0] == "ffmpeg" and isinstance(cmd, list)
    assert cmd[cmd.index("-f") + 1] == "concat" and cmd[cmd.index("-c") + 1] == "copy"
    assert "+faststart" in cmd and cmd[-1] == "/t/out.mp4" and "-nostdin" in cmd


def test_concat_list_quotes_paths():
    text = stitch.concat_list([Path("/a/one.mp4"), Path("/a/it's.mp4")])
    assert text.splitlines() == ["file '/a/one.mp4'", "file '/a/it'\\''s.mp4'"]


def test_reencode_command_without_audio():
    clips = [_clip(), _clip(width=640, height=360)]
    cmd = stitch.reencode_command("ffmpeg", [Path("/a.mp4"), Path("/b.mp4")], clips, Path("/o.mp4"))
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=704:1280" in graph and "concat=n=2:v=1:a=0[v]" in graph and "[a" not in graph
    assert "-an" in cmd and "libx264" in cmd and "yuv420p" in cmd and "+faststart" in cmd
    assert "aac" not in cmd and cmd.count("-i") == 2 and cmd[-1] == "/o.mp4"


def test_reencode_command_keeps_audio_only_if_every_clip_has_it():
    paths = [Path("/a.mp4"), Path("/b.mp4")]
    both = stitch.reencode_command("f", paths, [_clip(has_audio=True)] * 2, Path("/o.mp4"))
    assert "aac" in both and "concat=n=2:v=1:a=1[v][a]" in both[both.index("-filter_complex") + 1]
    mixed = stitch.reencode_command("f", paths, [_clip(has_audio=True), _clip()], Path("/o.mp4"))
    assert "aac" not in mixed and "-an" in mixed


def test_copy_only_when_every_clip_has_the_same_layout():
    assert stitch.can_copy([_clip(), _clip(), _clip()])
    assert not stitch.can_copy([_clip(), _clip(width=640)])
    assert not stitch.can_copy([_clip(), _clip(fps="30/1")])
    assert not stitch.can_copy([_clip(has_audio=True, audio_codec="aac"), _clip()])


def test_parse_probe():
    raw = json.dumps(
        {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 320, "height": 240,
                 "pix_fmt": "yuv420p", "avg_frame_rate": "24/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "3.04"},
        }
    )  # fmt: skip
    info = stitch.parse_probe(raw)
    assert (info.width, info.height, info.has_audio, info.duration) == (320, 240, True, 3.04)
    with pytest.raises(stitch.StitchError):
        stitch.parse_probe(json.dumps({"streams": [{"codec_type": "audio"}]}))


async def test_ffmpeg_timeout_kills_the_process():
    with pytest.raises(stitch.StitchError):
        await stitch._run(["sleep", "30"], 0.2)


# --- ffmpeg: real joins (skipped where ffmpeg is not installed) ----------------------------


def _make_clip(path: Path, size: str, seconds: int, fps: int = 24, audio: bool = False) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate={fps}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
    cmd += ["-t", str(seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-shortest"] if audio else []
    subprocess.run([*cmd, str(path)], check=True)  # noqa: S603


@needs_ffmpeg
async def test_real_join_copies_matching_clips(tmp_path):
    clips = [tmp_path / f"c{i}.mp4" for i in range(3)]
    for c in clips:
        _make_clip(c, "320x240", 2)
    out = tmp_path / "out.mp4"
    info = await stitch.concat_clips(clips, out)
    assert info.duration == pytest.approx(6, abs=0.3) and (info.width, info.height) == (320, 240)


@needs_ffmpeg
async def test_real_join_reencodes_clips_that_differ(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    _make_clip(a, "320x240", 2, fps=24)
    _make_clip(b, "640x360", 1, fps=30)
    out = tmp_path / "out.mp4"
    info = await stitch.concat_clips([a, b], out)
    assert info.duration == pytest.approx(3, abs=0.3) and (info.width, info.height) == (320, 240)


@needs_ffmpeg
async def test_real_join_with_audio(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    _make_clip(a, "320x240", 2, audio=True)
    _make_clip(b, "320x240", 2, audio=True)
    out = tmp_path / "out.mp4"
    info = await stitch.concat_clips([a, b], out)
    assert info.has_audio and info.duration == pytest.approx(4, abs=0.4)


@needs_ffmpeg
async def test_real_story_end_to_end_duration_is_the_sum_of_clips(alice):
    sid = (await create(alice)).json()["id"]
    await run_all()
    story = (await alice.get(f"/api/stories/{sid}")).json()
    assert story["status"] == "ready", story
    async with db.session_factory()() as s:
        asset = await s.get(Asset, story["final"]["id"])
    info = await stitch.probe(asset_path(asset.storage_key))
    assert info.duration == pytest.approx(9, abs=0.4)  # three 3 s demo clips
    assert asset.mime == "video/mp4" and asset.size_bytes > 0 and shutil.which("ffprobe")
