// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import type { InactiveModel, ModelInfo } from "../types";
import { formatInactiveModelLink, getModelFamily, shouldExpandInactive } from "./ModelPicker";

describe("ModelPicker - Inactive models section logic", () => {
  it("is collapsed by default when active models exist", () => {
    // When there are active models, section starts collapsed (false)
    expect(shouldExpandInactive(3)).toBe(false);
    expect(shouldExpandInactive(1)).toBe(false);
  });

  it("is expanded by default when no active models exist", () => {
    // When there are no active models, section starts expanded (true)
    expect(shouldExpandInactive(0)).toBe(true);
  });

  it("respects manual user toggle", () => {
    // If user clicked expand/collapse, that manual state overrides the default
    expect(shouldExpandInactive(5, true)).toBe(true);
    expect(shouldExpandInactive(5, false)).toBe(false);
    expect(shouldExpandInactive(0, false)).toBe(false);
    expect(shouldExpandInactive(0, true)).toBe(true);
  });

  it("links to Connect key in settings", () => {
    const mockInactive: InactiveModel = {
      provider_id: "openrouter_video",
      provider_name: "OpenRouter",
      id: "wan-video/wan-2.7-14b",
      label: "Wan 3.0 (14B)",
      kind: "video",
      commercial_use: "byok_only",
      reason: "Needs your OpenRouter key",
      price_text: "from ≈ 5¢ / s",
      price_cents: 5,
      key_url: "https://openrouter.ai/settings/keys",
      settings_path: "/settings",
    };

    const link = formatInactiveModelLink(mockInactive);
    expect(link.path).toBe("/settings");
    expect(link.labelKey).toBe("studio.connectKey");
  });
});

describe("ModelPicker - Family grouping logic", () => {
  const baseModel: ModelInfo = {
    id: "test",
    label: "Test",
    kind: "video",
    license: "test",
    commercial_use: "yes",
    aspect_ratios: ["16:9"],
    credit_cost: 10,
    max_count: 1,
    durations: [5],
    accepts_image: true,
    requires_image: false,
    upscale_targets: [],
    upscale_credits: {},
  };

  it("categorizes models into proper families", () => {
    expect(getModelFamily({ ...baseModel, id: "bytedance/seedance-2-5", label: "Seedance 2.5" })).toBe("Seedance");
    expect(getModelFamily({ ...baseModel, id: "black-forest-labs/flux-1-schnell", label: "FLUX.1 Schnell" })).toBe("FLUX");
    expect(getModelFamily({ ...baseModel, id: "wan-video/wan-2-1", label: "Wan 2.1 Video" })).toBe("Wan");
    expect(getModelFamily({ ...baseModel, id: "kwaivgi/kling-v1-5", label: "Kling 1.5" })).toBe("Kling");
    expect(getModelFamily({ ...baseModel, id: "minimax/hailuo", label: "Minimax Hailuo" })).toBe("Minimax Hailuo");
    expect(getModelFamily({ ...baseModel, id: "google/veo-2", label: "Google Veo 2" })).toBe("Google Veo");
    expect(getModelFamily({ ...baseModel, id: "openai/gpt-4o", label: "GPT-4o Vision" })).toBe("OpenAI");
  });
});
