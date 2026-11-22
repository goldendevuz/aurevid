// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { parseDirectorPlan } from "./director";
import { buildExpandRequest, readExpandedPrompt } from "./expand";

describe("buildExpandRequest", () => {
  it("sends duration, aspect and audio for video", () => {
    expect(buildExpandRequest({ prompt: "  a storm  ", kind: "video", durationSec: 15, aspect: "21:9", hasAudio: true })).toEqual({
      prompt: "a storm",
      kind: "video",
      aspect_ratio: "21:9",
      duration_sec: 15,
      has_audio: true,
    });
  });
  it("leaves video-only fields out for images", () => {
    const body = buildExpandRequest({ prompt: "a teapot", kind: "image", durationSec: 5, aspect: "1:1", hasAudio: true });
    expect(body).toEqual({ prompt: "a teapot", kind: "image", aspect_ratio: "1:1" });
    expect("duration_sec" in body).toBe(false);
    expect("has_audio" in body).toBe(false);
  });
  it("drops an invalid aspect ratio such as auto", () => {
    expect(buildExpandRequest({ prompt: "x y z", kind: "video", aspect: "auto" }).aspect_ratio).toBeUndefined();
  });
  it("caps the duration at the backend limit of 60 s", () => {
    expect(buildExpandRequest({ prompt: "x y z", kind: "video", durationSec: 120 }).duration_sec).toBe(60);
  });
  it("defaults has_audio to false for video when unknown", () => {
    expect(buildExpandRequest({ prompt: "x y z", kind: "video" }).has_audio).toBe(false);
  });
});

describe("readExpandedPrompt", () => {
  it("reads the `prompt` field the backend returns", () => {
    expect(readExpandedPrompt({ prompt: " Opening frame: a cat. ", cost_usd: 0.0004 })).toBe("Opening frame: a cat.");
  });
  it("returns null for empty, missing or legacy-shaped responses", () => {
    expect(readExpandedPrompt({ prompt: "  ", cost_usd: null })).toBeNull();
    expect(readExpandedPrompt(null)).toBeNull();
    expect(readExpandedPrompt({ expanded: "old shape" } as never)).toBeNull();
  });
});

describe("backend expansion format feeds the director parser", () => {
  const text = [
    "Opening frame: ultra-wide shot of a flooded street.",
    "Beat 1 (0-5 s) RISK: the current drags the bus. Camera: slow push-in.",
    "Beat 2 (5-10 s) RESCUE: the boat slams alongside. Camera: tracking shot.",
    "Look: stormy teal and amber dusk, photoreal.",
    "Audio: roaring water, rising strings.",
  ].join("\n");
  it("keeps two named beats, look and audio", () => {
    const plan = parseDirectorPlan(text);
    expect(plan.beats.map((b) => [b.timeRange, b.name])).toEqual([
      ["0-5 s", "RISK"],
      ["5-10 s", "RESCUE"],
    ]);
    expect(plan.look).toMatch(/teal/);
    expect(plan.audio).toMatch(/water/);
  });
});
