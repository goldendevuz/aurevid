// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import type { InactiveModel } from "../types";
import { formatInactiveModelLink, shouldExpandInactive } from "./ModelPicker";

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
