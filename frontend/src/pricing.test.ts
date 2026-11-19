// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { onFreeShare, priceOf } from "./pricing";
import type { ModelInfo, Provider } from "./types";

const model = { credit_cost: 2, upscale_credits: { "4k": 1, "8k": 3 } } as unknown as ModelInfo;

describe("priceOf", () => {
  it("multiplies the model cost by the count", () => {
    expect(priceOf(model, 3)).toEqual({ each: 2, count: 3, total: 6 });
  });
  it("adds upscale credits per output", () => {
    expect(priceOf(model, 2, "8k")).toEqual({ each: 5, count: 2, total: 10 });
    expect(priceOf(model, 2, "native").total).toBe(4);
  });
  it("is zero without a model", () => {
    expect(priceOf(undefined, 4).total).toBe(0);
  });
  it("knows when the shared key is used", () => {
    expect(onFreeShare({ key_source: "server" } as Provider)).toBe(true);
    expect(onFreeShare({ key_source: "user" } as Provider)).toBe(false);
  });
});
