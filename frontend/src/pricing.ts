// SPDX-License-Identifier: AGPL-3.0-or-later
// Upfront prices: the same formula the backend charges (routers/jobs.py), from catalog data.
import type { ModelInfo, Provider } from "./types";

export interface Price {
  each: number; // credits per output, upscaling included
  count: number;
  total: number;
}

/** The resolution a job without an explicit one gets (the backend's default). */
export function defaultResolution(model: ModelInfo | undefined): string | null {
  return model?.resolutions?.length ? (model.default_resolution ?? model.resolutions[0]) : null;
}

export function priceOf(
  model: ModelInfo | undefined,
  count = 1,
  upscale: string | null = null,
  resolution: string | null = null,
): Price {
  if (!model) return { each: 0, count, total: 0 };
  const extra = upscale && upscale !== "native" ? (model.upscale_credits[upscale] ?? 0) : 0;
  const res = resolution ?? defaultResolution(model);
  const resExtra = res ? (model.resolution_credits?.[res] ?? 0) : 0;
  const each = model.credit_cost + extra + resExtra;
  return { each, count, total: each * count };
}

/** Runs on the owner's shared key, so the user needs no key of their own (within the free share). */
export function onFreeShare(provider: Provider | undefined): boolean {
  return provider?.key_source === "server";
}
