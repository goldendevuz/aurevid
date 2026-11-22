// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { activeTier, estimatedUsd, expectedDimensions, fitLongSide, ignoresSize, isDraft, resolutionClass, usdLabel } from "./quality";
import { priceOf } from "./pricing";
import type { ModelInfo } from "./types";

const base: ModelInfo = {
  id: "m",
  label: "M",
  kind: "image",
  license: "x",
  commercial_use: "yes",
  aspect_ratios: ["1:1", "16:9"],
  credit_cost: 1,
  max_count: 1,
  durations: [],
  accepts_image: false,
  requires_image: false,
  upscale_targets: ["2k", "4k"],
  upscale_credits: { "2k": 1, "4k": 1 },
};
const wan: ModelInfo = { ...base, kind: "video", fixed_dimensions: { "16:9": [832, 480], "1:1": [640, 640] } };
const seedance: ModelInfo = {
  ...base,
  kind: "video",
  credit_cost: 10,
  resolutions: ["480p", "720p", "1080p"],
  default_resolution: "720p",
  resolution_credits: { "720p": 4, "1080p": 12 },
  resolution_sizes: { "480p": { "16:9": [854, 480] }, "720p": { "16:9": [1280, 720] }, "1080p": { "16:9": [1920, 1080] } },
  usd_per_second: { "720p": { "16:9": 0.2483 }, "1080p": { "16:9": 0.6084 } },
};

describe("draft marking", () => {
  it("marks 480p-class video and small images as drafts, 720p and 1024+ as not", () => {
    expect(isDraft("video/mp4", 832, 480)).toBe(true);
    expect(isDraft("video/mp4", 864, 496)).toBe(true);
    expect(isDraft("video/mp4", 480, 832)).toBe(true);
    expect(isDraft("video/mp4", 1280, 720)).toBe(false);
    expect(isDraft("video/mp4", 1080, 1920)).toBe(false);
    expect(isDraft("image/webp", 512, 512)).toBe(true);
    expect(isDraft("image/webp", 1024, 1024)).toBe(false);
    expect(isDraft("image/webp", 0, 0)).toBe(false);
  });
  it("names the real resolution class", () => {
    expect(resolutionClass("video/mp4", 832, 480)).toBe("480p");
    expect(resolutionClass("video/mp4", 1920, 1080)).toBe("1080p");
    expect(resolutionClass("video/mp4", 1280, 720)).toBe("720p");
    expect(resolutionClass("image/webp", 3840, 2160)).toBe("4K");
    expect(resolutionClass("image/webp", 2560, 1451)).toBe("2K");
    expect(resolutionClass("image/webp", 1024, 1024)).toBe("");
  });
});

describe("expected size is the real one, not the label", () => {
  it("fixed-size models ignore the Size choice", () => {
    for (const size of ["small", "medium", "large"]) expect(expectedDimensions(wan, { aspect: "16:9", size })).toEqual([832, 480]);
    expect(ignoresSize(wan)).toBe(true);
    expect(ignoresSize(base)).toBe(false);
  });
  it("size-aware models follow it, resolution models follow the resolution", () => {
    expect(expectedDimensions(base, { aspect: "16:9", size: "large" })).toEqual([1344, 768]);
    expect(expectedDimensions(base, { aspect: "1:1", size: "small" })).toEqual([512, 512]);
    expect(expectedDimensions(seedance, { aspect: "16:9", size: "large", resolution: "1080p" })).toEqual([1920, 1080]);
    expect(expectedDimensions(seedance, { aspect: "16:9", size: "large" })).toEqual([1280, 720]); // default 720p
  });
  it("publish quality renders at the model's largest side, then upscales", () => {
    const klein = { ...base, publish_max_side: 1920, publish_quality: true };
    expect(fitLongSide("16:9", 1920)).toEqual([1920, 1088]);
    expect(expectedDimensions(klein, { aspect: "16:9", size: "large", publish: true })).toEqual([1920, 1088]);
    expect(expectedDimensions(klein, { aspect: "16:9", size: "large", publish: true, upscale: "2k" })).toEqual([2560, 1451]);
    expect(expectedDimensions(klein, { aspect: "1:1", size: "large", publish: true, upscale: "4k" })).toEqual([3840, 3840]);
  });
});

describe("price display", () => {
  it("credits follow the resolution, default 720p for Seedance", () => {
    expect(priceOf(seedance).total).toBe(14);
    expect(priceOf(seedance, 1, null, "1080p").total).toBe(22);
    expect(priceOf(seedance, 1, null, "480p").total).toBe(10);
    expect(priceOf(base, 1, "2k").total).toBe(2);
  });
  it("USD estimate is rate x seconds, shown in cents under a dollar", () => {
    const usd = estimatedUsd(seedance, "720p", "16:9", 5)!;
    expect(usd).toBeCloseTo(1.2415, 3);
    expect(usdLabel(0.3241).short).toBe("32¢");
    expect(usdLabel(0.3241).exact).toBe("$0.3241");
    expect(usdLabel(usd).short).toBe("$1.24");
    expect(usdLabel(0.001).short).toBe("1¢");
    expect(estimatedUsd(wan, null, "16:9", 5)).toBeNull();
    expect(estimatedUsd(seedance, "1080p", "16:9", null)).toBeNull();
  });
  it("finds the active tier", () => {
    expect(activeTier("openrouter_video", "bytedance/seedance-2.0-mini", "480p")).toBe("draft");
    expect(activeTier("openrouter_video", "bytedance/seedance-2.5", "1080p")).toBe("premium");
    expect(activeTier("modal_video", "wan-2.2-ti2v-5b", null)).toBeNull();
  });
});
