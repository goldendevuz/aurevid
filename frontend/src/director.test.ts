// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import {
  buildDirectorJobPayload,
  buildDirectorStoryPayload,
  directorToStoryScenes,
  formatDirectorPrompt,
  parseDirectorPlan,
  shouldUseStory,
} from "./director";
import type { ModelInfo } from "./types";

describe("Director Plan Parser and Generator Helpers", () => {
  const sampleExpansion = `Opening frame: An astronaut stands alone on the rim of a glowing crater.
Beat 1 (0-5 s) - Arrival: The astronaut lowers their visor as dust storms sweep across the plains.
Beat 2 (5-10 s) - Encounter: A luminous alien artifact begins vibrating beneath the red soil.
Beat 3 (10-15 s) - Climax: Concentric rings of teal energy erupt into the twilight sky.
Look: 65mm IMAX format, hyper-detailed volumetric fog, warm cinematic orange and teal palette.
Audio: Ominous low-frequency synthesizer pulse blending with distant howling wind.`;

  it("parses structured expansion into a DirectorPlan object", () => {
    const plan = parseDirectorPlan(sampleExpansion);
    expect(plan.openingFrame).toBe("An astronaut stands alone on the rim of a glowing crater.");
    expect(plan.beats).toHaveLength(3);
    expect(plan.beats[0].timeRange).toBe("0-5 s");
    expect(plan.beats[0].name).toBe("Arrival");
    expect(plan.beats[0].text).toContain("The astronaut lowers their visor");
    expect(plan.beats[1].timeRange).toBe("5-10 s");
    expect(plan.beats[2].timeRange).toBe("10-15 s");
    expect(plan.look).toContain("65mm IMAX format");
    expect(plan.audio).toContain("Ominous low-frequency synthesizer");
  });

  it("is tolerant when Audio line is omitted", () => {
    const withoutAudio = `Opening frame: A lone samurai walks into a bamboo forest in mist.
Beat 1 (0-5 s) - Entrance: Bamboo stalks sway in quiet rain.
Beat 2 (5-10 s) - Stance: He draws his katana halfway from its scabbard.
Look: Monochromatic ink-wash aesthetic, high contrast black and white.`;

    const plan = parseDirectorPlan(withoutAudio);
    expect(plan.openingFrame).toBe("A lone samurai walks into a bamboo forest in mist.");
    expect(plan.beats).toHaveLength(2);
    expect(plan.look).toContain("Monochromatic ink-wash");
    expect(plan.audio).toBeUndefined();
  });

  it("re-formats an edited plan into a single coherent prompt", () => {
    const plan = {
      openingFrame: "A futuristic hovercraft accelerates down a highway.",
      beats: [
        { timeRange: "0-5 s", name: "Launch", text: "Thrusters fire bright blue flames." },
        { timeRange: "5-10 s", name: "Cruising", text: "It weaves between towering skyscrapers." },
      ],
      look: "Cyberpunk neon, wet asphalt reflections.",
      audio: "V8 futuristic engine roar.",
    };

    const formatted = formatDirectorPrompt(plan);
    expect(formatted).toContain("Opening frame: A futuristic hovercraft");
    expect(formatted).toContain("Beat 1 (0-5 s) - Launch: Thrusters fire");
    expect(formatted).toContain("Beat 2 (5-10 s) - Cruising: It weaves");
    expect(formatted).toContain("Look: Cyberpunk neon");
    expect(formatted).toContain("Audio: V8 futuristic engine");
  });

  it("correctly determines whether to create single clip or multi-scene story", () => {
    const fiveSecModel: ModelInfo = {
      id: "wan-5s",
      label: "Wan 5s",
      kind: "video",
      license: "test",
      commercial_use: "yes",
      aspect_ratios: ["16:9"],
      credit_cost: 5,
      max_count: 1,
      durations: [5],
      accepts_image: true,
      requires_image: false,
      upscale_targets: [],
      upscale_credits: {},
    };

    const tenSecModel: ModelInfo = {
      ...fiveSecModel,
      id: "seedance-10s",
      durations: [5, 10],
    };

    // 5s duration on a 5s max model -> single clip
    expect(shouldUseStory(5, fiveSecModel)).toBe(false);
    // 10s duration on a 5s max model -> multi-scene story
    expect(shouldUseStory(10, fiveSecModel)).toBe(true);
    // 10s duration on a 10s max model -> single clip
    expect(shouldUseStory(10, tenSecModel)).toBe(false);
    // 15s duration on a 10s max model -> multi-scene story
    expect(shouldUseStory(15, tenSecModel)).toBe(true);
  });

  it("converts plan beats to individual story scenes", () => {
    const plan = {
      openingFrame: "Start",
      beats: [
        { timeRange: "0-5 s", name: "Intro", text: "Sun rises over the mountains." },
        { timeRange: "5-10 s", name: "Outro", text: "Eagle takes flight." },
      ],
      look: "Golden hour lighting",
    };

    const scenes = directorToStoryScenes(plan);
    expect(scenes).toHaveLength(2);
    expect(scenes[0]).toBe("Intro: Sun rises over the mountains. (Golden hour lighting)");
    expect(scenes[1]).toBe("Outro: Eagle takes flight. (Golden hour lighting)");
  });

  it("builds the correct single-clip job payload from an edited plan", () => {
    const plan = {
      openingFrame: "A futuristic city in mist.",
      beats: [{ timeRange: "0-5 s", name: "Arrival", text: "A hovercar descends." }],
      look: "Neon reflections in puddles",
      audio: "Distant sirens",
    };

    const payload = buildDirectorJobPayload({
      plan,
      providerId: "openrouter",
      modelId: "bytedance/seedance-v1-pro",
      aspectRatio: "16:9",
      size: "large",
      duration: 5,
      resolution: "720p",
      startImageAssetId: "asset-123",
    });

    expect(payload.provider).toBe("openrouter");
    expect(payload.model).toBe("bytedance/seedance-v1-pro");
    expect(payload.aspect_ratio).toBe("16:9");
    expect(payload.count).toBe(1);
    expect(payload.duration).toBe(5);
    expect(payload.resolution).toBe("720p");
    expect(payload.image_asset_id).toBe("asset-123");
    expect(payload.prompt).toContain("Opening frame: A futuristic city in mist.");
    expect(payload.prompt).toContain("Beat 1 (0-5 s) - Arrival: A hovercar descends.");
    expect(payload.prompt).toContain("Look: Neon reflections in puddles");
    expect(payload.prompt).toContain("Audio: Distant sirens");
  });

  it("builds the correct multi-scene story payload from an edited plan", () => {
    const plan = {
      openingFrame: "Opening",
      beats: [
        { timeRange: "0-5 s", name: "Beat 1", text: "First scene action." },
        { timeRange: "5-10 s", name: "Beat 2", text: "Second scene action." },
      ],
      look: "Cinematic 35mm",
    };

    const payload = buildDirectorStoryPayload({
      plan,
      providerId: "openrouter",
      modelId: "kuaishou/kling-v1.6-pro",
      aspectRatio: "9:16",
      resolution: "1080p",
    });

    expect(payload.provider).toBe("openrouter");
    expect(payload.model).toBe("kuaishou/kling-v1.6-pro");
    expect(payload.aspect_ratio).toBe("9:16");
    expect(payload.resolution).toBe("1080p");
    expect(payload.scenes).toEqual([
      "Beat 1: First scene action. (Cinematic 35mm)",
      "Beat 2: Second scene action. (Cinematic 35mm)",
    ]);
  });
});
