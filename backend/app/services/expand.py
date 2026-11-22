# SPDX-License-Identifier: AGPL-3.0-or-later
"""Expand a one-line idea into a detailed, structured prompt using an LLM via OpenRouter."""

import logging
import math
import re

import httpx

from app.config import get_settings

log = logging.getLogger("aurevid.expand")

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# System prompts (from the reference bundle, stored as constants)
# ---------------------------------------------------------------------------

# fmt: off
SYSTEM_PROMPT_VIDEO = (  # noqa: E501
    "You are a prompt writer for AI video models (Seedance and similar)."
    " Turn the user's one-line idea into one detailed, sequenced scene prompt.\n"
    "Rules:\n"
    "- Write in English. If the idea contains names, quoted text or non-English"
    " words, keep them exactly as given. Keep the user's idea and intent;"
    " add detail, do not change the subject.\n"
    "- Plain text only: no markdown, no asterisks, no preamble, no closing remarks.\n"
    "- Use exactly this structure, one item per line:\n"
    "  Opening frame: one sentence describing the first image. Everything that"
    " matters later (every main subject, vehicle, creature or place, including"
    " the threat or target) must already be visible or clearly implied in this"
    " frame, and the framing must suit the aspect ratio (wide aspect ratios:"
    " wide, layered composition with foreground, midground and background).\n"
    "  Then one line per beat, in the given order, formatted \"Beat N (A-B s)"
    " NAME: what happens. Camera: one continuous camera move for this beat.\""
    " NAME is a single capitalised word for the beat (for example PILOT,"
    " MISSILE, IMPACT).\n"
    "  Look: one line with lighting, colour palette and visual style.\n"
    "  Audio: one line with sub-bass, sound effects and score."
    " (Include this line only when audio is on.)\n"
    "- Story: the beats are one cause-and-effect chain with a clear stake."
    " First beat: who or what is in danger or under pressure, shown through"
    " a person, crew, creature or place we can care about (give a human or"
    " character face/reaction when it fits the idea). Middle beat(s): the"
    " action that follows. Last beat: the consequence, not just the event."
    " Show what the action caused and end on a settled final image (aftermath,"
    " reveal, silhouette), never on an explosion or peak action alone.\n"
    "- Tone: honour the energy words in the idea. \"Epic\", \"dramatic\","
    " \"intense\", \"battle\", \"chase\" or \"action\" mean real conflict,"
    " danger and scale: pick the most cinematic high-stakes situation (a"
    " battle, chase, escape, collapse) with an opponent or threat that is"
    " visible, and never settle for a calm journey, travel or sightseeing"
    " scene. When the idea is vague, choose the most dramatic interpretation"
    " that fits it. Calm ideas stay calm.\n"
    "- Keep the action readable for a video model: one main subject and at"
    " most two or three secondary moving objects per beat (for example one or"
    " two missiles, not a volley or swarm); no crowds of tiny objects; no more"
    " than one scene change in the whole clip; keep the same subjects, colours"
    " and positions consistent across beats.\n"
    "- Density: each beat holds exactly ONE main action (one sentence) plus at"
    " most one short reaction or detail; never stack several events (fire,"
    " dodge, sparks, collapse) in one beat. Length limits per line: Opening"
    " frame up to 240 characters, each Beat up to 170 characters, Look up to"
    " 110, Audio up to 110. The whole answer stays under 1000 characters;"
    " count and shorten before answering.\n"
    "- Camera: one simple, physically plausible move per beat (push-in,"
    " pull-back, pan, tracking, crane, orbit). Do not combine several moves"
    " in one beat.\n"
    "- Never contradict the Audio line in the beats: when audio is on, do not"
    " describe events as silent, soundless or quiet unless the Audio line says"
    " so; describe the visual event only and let the Audio line carry the"
    " sound. Name where every shot, missile, beam or attack comes from (which"
    " side, ship or character) and where it goes.\n"
    "- For wide aspect ratios (21:9, 16:9) the Opening frame must literally"
    " say \"wide\" or \"ultra-wide\" and name a foreground, a midground and a"
    " background element.\n"
    "- Make sound consistent with the look: realistic style keeps sound"
    " physically believable, stylised style may be bolder; the Audio line must"
    " match the events of the beats in order.\n"
    "- Worked example of the quality and format wanted (a different idea;"
    " reference only, never copy its subject, places or wording). Idea"
    " \"a dramatic flood rescue\", 10 s, 16:9, audio on:\n"
    "Opening frame: ultra-wide shot of a flooded street at dusk, a rescue boat"
    " in the foreground with a soaked firefighter at the bow, a half-submerged"
    " bus with a child waving from its roof in the midground, a collapsing"
    " bridge in the background.\n"
    "Beat 1 (0-5 s) RISK: the current drags the bus sideways as the"
    " firefighter fights the throttle and shouts toward the child. Camera:"
    " slow push-in on the firefighter's strained face.\n"
    "Beat 2 (5-10 s) RESCUE: the boat slams alongside, the firefighter lunges"
    " and pulls the child aboard as the bridge groans behind them. Camera:"
    " smooth tracking shot along the boat.\n"
    "Look: stormy teal and amber dusk light, wet reflections, high contrast,"
    " photoreal.\n"
    "Audio: roaring water, creaking metal, a shouted warning, rising strings"
    " that resolve on a calm low chord.\n"
    "- Never mention brands, logos, watermarks, subtitles or real people."
    " Do not name real celebrities or copyrighted characters.\n"
    "- Never drop the Look or Audio line to fit: write shorter beats instead."
)

SYSTEM_PROMPT_IMAGE = (
    "You are a prompt writer for AI image models."
    " Turn the user's one-line idea into one detailed image prompt.\n"
    "Rules:\n"
    "- Write in English. If the idea contains names, quoted text or"
    " non-English words, keep them exactly as given. Keep the user's"
    " idea and intent; add detail, do not change the subject.\n"
    "- Plain text only: no markdown, no asterisks, no preamble,"
    " no closing remarks.\n"
    "- Use exactly this structure, one item per line:\n"
    "  Subject: who or what, with specific visual details.\n"
    "  Setting: place, time of day, atmosphere.\n"
    "  Composition: framing, lens and camera angle suited to the"
    " aspect ratio.\n"
    "  Look: lighting, colour palette and style.\n"
    "- Never mention brands, logos, watermarks, text overlays or real"
    " people. Do not name real celebrities or copyrighted characters.\n"
    "- Keep the whole answer under 800 characters."
)
# fmt: on


# ---------------------------------------------------------------------------
# Beat-plan builder
# ---------------------------------------------------------------------------


def beat_plan(duration_sec: int) -> list[tuple[int, int]]:
    """Return a list of (start, end) second pairs for video beats.

    Formula:
      total = max(1, round(duration))
      count = min(6, max(1, ceil(total/5)))
      beat i ends at round(total*i/count), starts at previous end (first start 0).
    """
    total = max(1, round(duration_sec))
    count = min(6, max(1, math.ceil(total / 5)))
    beats = []
    prev = 0
    for i in range(1, count + 1):
        end = round(total * i / count)
        beats.append((prev, end))
        prev = end
    return beats


# ---------------------------------------------------------------------------
# User-message builder
# ---------------------------------------------------------------------------


def build_user_message(
    *,
    prompt: str,
    kind: str,
    duration_sec: int | None = None,
    aspect_ratio: str | None = None,
    has_audio: bool = True,
) -> str:
    """Build the user message for the LLM call."""
    lines = [f"Idea: {prompt}"]

    if kind == "video":
        dur = duration_sec or 5
        lines.append(f"Clip length: {dur} s")
        if aspect_ratio and aspect_ratio != "auto":
            lines.append(f"Aspect ratio: {aspect_ratio} (compose the framing for it)")
        beats = beat_plan(dur)
        beat_strs = ", ".join(f"Beat {i + 1} {s}-{e} s" for i, (s, e) in enumerate(beats))
        lines.append(f"Beats ({len(beats)}): {beat_strs}")
        if has_audio:
            lines.append("Audio: on. Include the Audio line.")
        else:
            lines.append("Audio: off. Do NOT write an Audio line and do not mention sound.")
    else:  # image
        if aspect_ratio and aspect_ratio != "auto":
            lines.append(f"Aspect ratio: {aspect_ratio}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response cleanup
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_MD_RE = re.compile(r"\*\*|__|`+|^#+\s", re.MULTILINE)
_MULTI_NL = re.compile(r"\n{3,}")
HARD_CAP = 1600


def _length_cap() -> int:
    """Cap at what a job prompt may hold (MAX_PROMPT_CHARS); longer text could not be submitted."""
    return min(HARD_CAP, get_settings().max_prompt_chars)


def cleanup(text: str) -> str:
    """Strip model artifacts and enforce length cap."""
    text = _THINK_RE.sub("", text)
    text = _MD_RE.sub("", text)
    text = _MULTI_NL.sub("\n\n", text)
    text = text.strip()

    cap = _length_cap()
    if len(text) <= cap:
        return text

    # Try to cut at the last line break or ". " that keeps > 60% of cap.
    threshold = int(cap * 0.6)
    candidate = text[:cap]

    # Try line break first
    pos = candidate.rfind("\n")
    if pos >= threshold:
        return candidate[:pos].rstrip()

    # Try sentence boundary
    pos = candidate.rfind(". ")
    if pos >= threshold:
        return candidate[: pos + 1].rstrip()

    return candidate.rstrip()


# ---------------------------------------------------------------------------
# Completeness check (video only)
# ---------------------------------------------------------------------------


def is_complete(text: str, has_audio: bool) -> bool:
    """Check if a video response has the required Look: and Audio: lines."""
    has_look = any(line.strip().startswith("Look:") for line in text.splitlines())
    has_audio_line = any(line.strip().startswith("Audio:") for line in text.splitlines())
    if not has_look:
        return False
    if has_audio and not has_audio_line:
        return False
    if len(text) > min(1350, _length_cap()):
        return False
    return True


def pick_best(first: str, second: str | None, has_audio: bool) -> str:
    """Pick the best response: first complete, else shorter, else first."""
    if is_complete(first, has_audio):
        return first
    if second is not None and is_complete(second, has_audio):
        return second
    # Neither is fully complete; pick the one with required lines if any
    if second is not None:

        def has_lines(t: str) -> bool:
            look = any(ln.strip().startswith("Look:") for ln in t.splitlines())
            aud = any(ln.strip().startswith("Audio:") for ln in t.splitlines())
            return look and (aud or not has_audio)

        if has_lines(second) and not has_lines(first):
            return second
        if has_lines(first) and has_lines(second):
            return first if len(first) <= len(second) else second
    return first


# ---------------------------------------------------------------------------
# Main expand function
# ---------------------------------------------------------------------------


async def expand_prompt(
    *,
    prompt: str,
    kind: str,
    duration_sec: int | None = None,
    aspect_ratio: str | None = None,
    has_audio: bool = True,
    api_key: str,
) -> tuple[str, float | None]:
    """Expand a prompt using OpenRouter chat completions.

    Returns (expanded_text, cost_usd_or_none).
    Raises ExpandError on failure.
    """
    s = get_settings()
    model = s.expand_model

    system_prompt = SYSTEM_PROMPT_VIDEO if kind == "video" else SYSTEM_PROMPT_IMAGE
    user_message = build_user_message(
        prompt=prompt,
        kind=kind,
        duration_sec=duration_sec,
        aspect_ratio=aspect_ratio,
        has_audio=has_audio,
    )

    total_cost: float | None = 0.0
    first_text: str | None = None
    attempts = 2 if kind == "video" else 1

    for attempt in range(attempts):
        text, cost = await _call_llm(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
        )
        text = cleanup(text)
        if total_cost is not None and cost is not None:
            total_cost += cost
        else:
            total_cost = None

        if attempt == 0:
            first_text = text

        # For image prompts, no completeness check
        if kind != "video":
            return text, total_cost

        # Video: check completeness
        if is_complete(text, has_audio):
            return text, total_cost

        # First attempt incomplete, try again (only once)
        if attempt == 0:
            continue

    # After both attempts, pick the best
    assert first_text is not None
    best = pick_best(first_text, text, has_audio)
    return best, total_cost


class ExpandError(Exception):
    """Raised when the expand call fails."""

    def __init__(self, code: str, status_code: int = 500):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


async def _call_llm(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_message: str,
) -> tuple[str, float | None]:
    """Single call to OpenRouter chat/completions. Returns (text, cost)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 900,
        "temperature": 0.6,
        "reasoning": {"enabled": False},
    }

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False,
        ) as client:
            resp = await client.post(
                OPENROUTER_CHAT_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.TimeoutException:
        raise ExpandError("expand_timeout", 504) from None
    except httpx.HTTPError:
        raise ExpandError("expand_timeout", 504) from None

    if resp.status_code == 429:
        raise ExpandError("expand_busy", 429)

    if resp.status_code in (401, 402, 403):
        log.warning("expand upstream auth error status=%d", resp.status_code)
        raise ExpandError("expand_unavailable", 503)

    if resp.status_code >= 400:
        log.warning("expand upstream error status=%d", resp.status_code)
        raise ExpandError("expand_failed", 502)

    try:
        data = resp.json()
    except Exception:
        raise ExpandError("expand_failed", 502) from None

    # Extract text
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ExpandError("expand_empty", 502) from None

    if not content or not content.strip():
        raise ExpandError("expand_empty", 502)

    # Extract cost (may not be present)
    cost: float | None = None
    usage = data.get("usage", {})
    if usage.get("total_cost") is not None:
        cost = float(usage["total_cost"])

    return content.strip(), cost
