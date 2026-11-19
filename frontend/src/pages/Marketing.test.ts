// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import type { ModelInfo, Provider } from "../types";
import { pickAdModel } from "./Marketing";

const model = (id: string, extra: Partial<ModelInfo> = {}): ModelInfo => ({
  id, label: id, kind: "image", license: "x", commercial_use: "yes", aspect_ratios: ["1:1", "9:16"],
  credit_cost: 1, max_count: 4, durations: [], accepts_image: false, requires_image: false,
  upscale_targets: [], upscale_credits: {}, ...extra,
});
const provider = (id: string, tier: "free" | "paid", models: ModelInfo[], available = true) =>
  ({ id, name: id, tier, available, models }) as unknown as Provider;

describe("pickAdModel", () => {
  it("prefers an available free commercial image model with the format", () => {
    const ps = [
      provider("paid", "paid", [model("cheap", { credit_cost: 0 })]),
      provider("off", "free", [model("off")], false),
      provider("free", "free", [model("nc", { commercial_use: "no" }), model("sq", { aspect_ratios: ["1:1"] }), model("ok", { credit_cost: 2 })]),
    ];
    expect(pickAdModel(ps, "9:16")?.m.id).toBe("ok");
    expect(pickAdModel(ps, "1:1")?.m.id).toBe("sq");
  });
  it("falls back to the cheapest paid model, or nothing", () => {
    expect(pickAdModel([provider("p", "paid", [model("a", { credit_cost: 5 }), model("b", { credit_cost: 3 })])], "1:1")?.m.id).toBe("b");
    expect(pickAdModel([provider("p", "paid", [model("v", { kind: "video" })])], "1:1")).toBeUndefined();
  });
});
