# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for /api/prompt/expand and services/expand.py."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import get_settings
from app.services.expand import (
    beat_plan,
    build_user_message,
    cleanup,
    is_complete,
    pick_best,
)
from tests.conftest import csrf_headers

# ---------------------------------------------------------------------------
# Unit tests: beat_plan
# ---------------------------------------------------------------------------


class TestBeatPlan:
    """Beat plan must match the spec table exactly."""

    @pytest.mark.parametrize(
        "dur,expected",
        [
            (4, [(0, 4)]),
            (5, [(0, 5)]),
            (6, [(0, 3), (3, 6)]),
            (10, [(0, 5), (5, 10)]),
            (15, [(0, 5), (5, 10), (10, 15)]),
            (
                30,
                [
                    (0, 5),
                    (5, 10),
                    (10, 15),
                    (15, 20),
                    (20, 25),
                    (25, 30),
                ],
            ),
        ],
    )
    def test_beat_plan_table(self, dur, expected):
        assert beat_plan(dur) == expected

    def test_beat_plan_1_second(self):
        assert beat_plan(1) == [(0, 1)]

    def test_beat_plan_zero_clamps(self):
        """duration < 1 clamps to 1."""
        assert beat_plan(0) == [(0, 1)]


# ---------------------------------------------------------------------------
# Unit tests: build_user_message
# ---------------------------------------------------------------------------


class TestBuildUserMessage:
    def test_video_audio_on(self):
        msg = build_user_message(
            prompt="a cat",
            kind="video",
            duration_sec=10,
            aspect_ratio="16:9",
            has_audio=True,
        )
        assert "Idea: a cat" in msg
        assert "Clip length: 10 s" in msg
        assert "Aspect ratio: 16:9" in msg
        assert "Beats (2): Beat 1 0-5 s, Beat 2 5-10 s" in msg
        assert "Audio: on. Include the Audio line." in msg

    def test_video_audio_off(self):
        msg = build_user_message(prompt="a dog", kind="video", duration_sec=5, has_audio=False)
        assert "Audio: off. Do NOT write an Audio line" in msg
        assert "Audio: on" not in msg

    def test_video_no_aspect(self):
        msg = build_user_message(prompt="fire", kind="video", duration_sec=5)
        assert "Aspect ratio" not in msg

    def test_video_auto_aspect(self):
        msg = build_user_message(
            prompt="fire",
            kind="video",
            duration_sec=5,
            aspect_ratio="auto",
        )
        assert "Aspect ratio" not in msg

    def test_image_with_aspect(self):
        msg = build_user_message(prompt="a sunset", kind="image", aspect_ratio="1:1")
        assert "Idea: a sunset" in msg
        assert "Aspect ratio: 1:1" in msg
        assert "Beat" not in msg
        assert "Audio" not in msg

    def test_image_no_aspect(self):
        msg = build_user_message(prompt="a sunset", kind="image")
        assert "Aspect ratio" not in msg


# ---------------------------------------------------------------------------
# Unit tests: cleanup
# ---------------------------------------------------------------------------


class TestCleanup:
    def test_strips_think_tags(self):
        text = "<think>internal reasoning</think>Hello world"
        assert cleanup(text) == "Hello world"

    def test_strips_markdown(self):
        text = "**bold** and __underline__ and `code` and # heading"
        result = cleanup(text)
        assert "**" not in result
        assert "__" not in result
        assert "`" not in result
        assert result.startswith("bold")

    def test_collapses_newlines(self):
        text = "line1\n\n\n\nline2"
        assert cleanup(text) == "line1\n\nline2"

    def test_hard_cap(self):
        text = "x" * 2000
        result = cleanup(text)
        assert len(result) <= 1600

    def test_cuts_at_line_break(self):
        """Cut at a line break if it keeps > 60% of cap."""
        text = ("A" * 1200) + "\n" + ("B" * 500)
        result = cleanup(text)
        assert len(result) <= 1600
        assert result.endswith("A" * 1200)

    def test_cuts_at_sentence(self):
        """Cut at '. ' if no good line break."""
        text = ("A" * 1200) + ". " + ("B" * 500)
        result = cleanup(text)
        assert len(result) <= 1600
        assert result.endswith("A" * 1200 + ".")


# ---------------------------------------------------------------------------
# Unit tests: completeness
# ---------------------------------------------------------------------------


class TestCompleteness:
    def test_complete_video(self):
        text = "Opening frame: ...\nBeat 1: ...\nLook: warm\nAudio: boom"
        assert is_complete(text, has_audio=True)

    def test_missing_audio(self):
        text = "Opening frame: ...\nBeat 1: ...\nLook: warm"
        assert not is_complete(text, has_audio=True)

    def test_no_audio_needed(self):
        text = "Opening frame: ...\nBeat 1: ...\nLook: warm"
        assert is_complete(text, has_audio=False)

    def test_missing_look(self):
        text = "Opening frame: ...\nBeat 1: ...\nAudio: boom"
        assert not is_complete(text, has_audio=True)

    def test_too_long(self):
        text = "Look: warm\nAudio: boom\n" + "x" * 1400
        assert not is_complete(text, has_audio=True)

    def test_pick_best_first_complete(self):
        good = "Look: x\nAudio: y"
        bad = "no look"
        assert pick_best(good, bad, has_audio=True) == good

    def test_pick_best_second_complete(self):
        bad = "no look"
        good = "Look: x\nAudio: y"
        assert pick_best(bad, good, has_audio=True) == good

    def test_pick_best_neither_complete(self):
        a = "Look: x"  # missing Audio
        b = "Look: y\nAudio: z" + "x" * 1400  # too long
        result = pick_best(a, b, has_audio=True)
        # b has the required lines, a does not
        assert result == b


# ---------------------------------------------------------------------------
# Integration tests: router /api/prompt/expand
# ---------------------------------------------------------------------------

GOOD_VIDEO = (
    "Opening frame: a cat.\nBeat 1 (0-5 s) CAT: cat walks.\nLook: warm light.\nAudio: soft purr."
)
GOOD_IMAGE = "Subject: a sunset.\nSetting: beach at dusk.\nComposition: wide angle.\nLook: golden."
INCOMPLETE_VIDEO = "Opening frame: a cat.\nBeat 1 (0-5 s) CAT: cat walks."


def _mock_response(content: str, cost: float = 0.001, sc: int = 200):
    """Build a mock httpx.Response for a successful LLM call."""
    return httpx.Response(
        sc,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"total_cost": cost},
        },
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


def _mock_error_response(status_code: int):
    return httpx.Response(
        status_code,
        json={"error": {"message": "fail"}},
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


@pytest.fixture
def server_key():
    s = get_settings()
    s.openrouter_api_key = "mock-test-key-for-expand"
    yield
    s.openrouter_api_key = ""


def _patch_client(post_side_effect=None, post_return=None):
    """Return a patch context for httpx.AsyncClient."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    if post_side_effect is not None:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    elif post_return is not None:
        mock_client.post = AsyncMock(return_value=post_return)
    return mock_client


@pytest.mark.usefixtures("server_key")
class TestExpandRouter:
    async def test_auth_required(self, anon):
        await anon.get("/api/auth/csrf")
        r = await anon.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "video"},
            headers=csrf_headers(anon),
        )
        assert r.status_code == 401

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_success_video(self, mock_cls, alice):
        mock_cls.return_value = _patch_client(post_return=_mock_response(GOOD_VIDEO))
        r = await alice.post(
            "/api/prompt/expand",
            json={
                "prompt": "a dramatic cat chase",
                "kind": "video",
                "duration_sec": 5,
            },
            headers=csrf_headers(alice),
        )
        assert r.status_code == 200
        data = r.json()
        assert "Look:" in data["prompt"]
        assert data["cost_usd"] is not None

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_success_image(self, mock_cls, alice):
        mock_cls.return_value = _patch_client(post_return=_mock_response(GOOD_IMAGE))
        r = await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a sunset", "kind": "image"},
            headers=csrf_headers(alice),
        )
        assert r.status_code == 200
        assert "Subject:" in r.json()["prompt"]

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_completeness_retry(self, mock_cls, alice):
        """Incomplete first -> call twice, pick the good one."""
        mc = _patch_client(
            post_side_effect=[
                _mock_response(INCOMPLETE_VIDEO, cost=0.001),
                _mock_response(GOOD_VIDEO, cost=0.002),
            ]
        )
        mock_cls.return_value = mc
        r = await alice.post(
            "/api/prompt/expand",
            json={
                "prompt": "a cat",
                "kind": "video",
                "duration_sec": 5,
            },
            headers=csrf_headers(alice),
        )
        assert r.status_code == 200
        data = r.json()
        assert "Look:" in data["prompt"]
        assert "Audio:" in data["prompt"]
        assert data["cost_usd"] == pytest.approx(0.003)
        assert mc.post.call_count == 2

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_no_retry_on_500(self, mock_cls, alice):
        mc = _patch_client(post_return=_mock_error_response(500))
        mock_cls.return_value = mc
        r = await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "video"},
            headers=csrf_headers(alice),
        )
        assert r.status_code == 502
        assert r.json()["detail"]["code"] == "expand_failed"
        assert mc.post.call_count == 1

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_error_401(self, mock_cls, alice):
        mock_cls.return_value = _patch_client(post_return=_mock_error_response(401))
        r = await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "video"},
            headers=csrf_headers(alice),
        )
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "expand_unavailable"

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_error_429(self, mock_cls, alice):
        mock_cls.return_value = _patch_client(post_return=_mock_error_response(429))
        r = await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "video"},
            headers=csrf_headers(alice),
        )
        assert r.status_code == 429
        assert r.json()["detail"]["code"] == "expand_busy"

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_error_timeout(self, mock_cls, alice):
        mock_cls.return_value = _patch_client(post_side_effect=httpx.TimeoutException("timeout"))
        r = await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "video"},
            headers=csrf_headers(alice),
        )
        assert r.status_code == 504
        assert r.json()["detail"]["code"] == "expand_timeout"

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_error_empty(self, mock_cls, alice):
        mock_cls.return_value = _patch_client(
            post_return=httpx.Response(
                200,
                json={"choices": [{"message": {"content": ""}}]},
                request=httpx.Request(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                ),
            )
        )
        r = await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "video"},
            headers=csrf_headers(alice),
        )
        assert r.status_code == 502
        assert r.json()["detail"]["code"] == "expand_empty"

    async def test_rate_limit(self, alice):
        """21st call should get 429."""
        with patch("app.services.expand.httpx.AsyncClient") as mc:
            mc.return_value = _patch_client(post_return=_mock_response(GOOD_IMAGE))
            for i in range(20):
                r = await alice.post(
                    "/api/prompt/expand",
                    json={"prompt": f"test {i}", "kind": "image"},
                    headers=csrf_headers(alice),
                )
                assert r.status_code == 200, f"#{i + 1}: {r.text}"

            r = await alice.post(
                "/api/prompt/expand",
                json={"prompt": "one more", "kind": "image"},
                headers=csrf_headers(alice),
            )
            assert r.status_code == 429

    async def test_no_key_503(self, alice):
        """No user or server key -> 503."""
        s = get_settings()
        s.openrouter_api_key = ""
        r = await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "video"},
            headers=csrf_headers(alice),
        )
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "expand_unavailable"

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_key_not_in_logs(self, mock_cls, alice, caplog):
        """The API key must never appear in logs."""
        mock_cls.return_value = _patch_client(post_return=_mock_response(GOOD_IMAGE))
        with caplog.at_level(logging.DEBUG):
            r = await alice.post(
                "/api/prompt/expand",
                json={"prompt": "a cat", "kind": "image"},
                headers=csrf_headers(alice),
            )
        assert r.status_code == 200
        assert "mock-test-key-for-expand" not in caplog.text
        assert "mock-test-key-for-expand" not in r.text

    @patch("app.services.expand.httpx.AsyncClient")
    async def test_redirect_disabled(self, mock_cls, alice):
        """httpx client has follow_redirects=False."""
        mock_cls.return_value = _patch_client(post_return=_mock_response(GOOD_IMAGE))
        await alice.post(
            "/api/prompt/expand",
            json={"prompt": "a cat", "kind": "image"},
            headers=csrf_headers(alice),
        )
        mock_cls.assert_called_once()
        kw = mock_cls.call_args
        assert kw.kwargs.get("follow_redirects") is False


# ---------------------------------------------------------------------------
# /api/me should include expand_available
# ---------------------------------------------------------------------------


class TestExpandAvailable:
    async def test_with_server_key(self, alice):
        s = get_settings()
        s.openrouter_api_key = "mock-key"
        r = await alice.get("/api/me")
        assert r.status_code == 200
        assert r.json()["expand_available"] is True
        s.openrouter_api_key = ""

    async def test_without_key(self, alice):
        s = get_settings()
        s.openrouter_api_key = ""
        r = await alice.get("/api/me")
        assert r.status_code == 200
        assert r.json()["expand_available"] is False
