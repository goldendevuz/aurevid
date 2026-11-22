// SPDX-License-Identifier: AGPL-3.0-or-later
// What a result really is: real pixel sizes, "Draft" marking, expected output sizes and USD estimates.
// Mirrors the backend (providers/base.py output_dimensions / fit_long_side) so the UI never
// reports the requested label instead of the real resolution.
import { defaultResolution } from "./pricing";
import type { Job, ModelInfo } from "./types";

/** Videos shorter than 720 px and images under 1024 px are drafts: fine to review, not to publish. */
export const DRAFT_VIDEO_SHORT_SIDE = 720;
export const DRAFT_IMAGE_LONG_SIDE = 1024;

export function isDraft(mime: string, width: number, height: number): boolean {
  if (!width || !height) return false;
  return mime.startsWith("video/") ? Math.min(width, height) < DRAFT_VIDEO_SHORT_SIDE : Math.max(width, height) < DRAFT_IMAGE_LONG_SIDE;
}

/** A job's draft status from the real file when there is one, else from the expected size. */
export function isDraftJob(job: Job): boolean {
  const a = job.assets[0];
  if (a) return isDraft(a.mime, a.width, a.height);
  return isDraft(job.kind === "video" ? "video/mp4" : "image/webp", job.params.width, job.params.height);
}

export const sizeText = (w: number, h: number) => `${w}×${h}`;

/** "480p", "720p", "1080p" for video; "2K", "4K", "8K" by long side for images; else "". */
export function resolutionClass(mime: string, w: number, h: number): string {
  if (mime.startsWith("video/")) {
    const short = Math.min(w, h);
    return short >= 1800 ? "4K" : short >= 1000 ? "1080p" : short >= 700 ? "720p" : short >= 460 ? "480p" : `${short}p`;
  }
  const long = Math.max(w, h);
  return long >= 7680 ? "8K" : long >= 3840 ? "4K" : long >= 2560 ? "2K" : "";
}

const ASPECTS: Record<string, [number, number]> = {
  "1:1": [1024, 1024],
  "16:9": [1344, 768],
  "9:16": [768, 1344],
  "4:3": [1152, 896],
  "3:4": [896, 1152],
};
const SCALE: Record<string, number> = { small: 0.5, medium: 0.75, large: 1 };
const TARGET_LONG: Record<string, number> = { "2k": 2560, "4k": 3840, "8k": 7680 };

function sizeFor(aspect: string, size: string): [number, number] {
  const [w, h] = ASPECTS[aspect] ?? ASPECTS["1:1"];
  const k = SCALE[size] ?? 1;
  return [Math.floor(Math.floor(w * k) / 64) * 64, Math.floor(Math.floor(h * k) / 64) * 64];
}

/** Largest size of this aspect ratio with the given long side, on the 64 px grid. */
export function fitLongSide(aspect: string, longSide: number): [number, number] {
  const [w, h] = ASPECTS[aspect] ?? ASPECTS["1:1"];
  const k = longSide / Math.max(w, h);
  const fit = (side: number) => (side === Math.max(w, h) ? longSide : Math.max(64, Math.round((side * k) / 64) * 64));
  return [fit(w), fit(h)];
}

export interface OutputOptions {
  aspect: string;
  size: string;
  resolution?: string | null;
  publish?: boolean;
  upscale?: string | null; // "2k" | "4k" | "8k" | null | "native"
}

/** The real size a result will have (the file's own size replaces it once it exists). */
export function expectedDimensions(model: ModelInfo | undefined, o: OutputOptions): [number, number] | null {
  if (!model) return null;
  let base: [number, number];
  if (o.publish && model.publish_max_side) base = fitLongSide(o.aspect, model.publish_max_side);
  else if (model.resolution_sizes && defaultResolution(model)) {
    const sizes = model.resolution_sizes[o.resolution ?? defaultResolution(model)!] ?? {};
    base = sizes[o.aspect] ?? Object.values(sizes)[0] ?? sizeFor(o.aspect, o.size);
  } else if (model.fixed_dimensions?.[o.aspect]) base = model.fixed_dimensions[o.aspect];
  else base = sizeFor(o.aspect, o.size);
  const target = o.upscale && o.upscale !== "native" ? TARGET_LONG[o.upscale] : undefined;
  if (model.kind === "image" && target && target > Math.max(...base)) {
    const k = target / Math.max(...base);
    return [Math.round(base[0] * k), Math.round(base[1] * k)];
  }
  return base;
}

/** True when the Size choice changes nothing for this model (fixed or resolution-based output). */
export function ignoresSize(model: ModelInfo | undefined): boolean {
  return !!model && (!!model.resolutions?.length || Object.keys(model.fixed_dimensions ?? {}).length > 0);
}

/** Estimated USD for one clip, or null when the model is not priced per second. */
export function estimatedUsd(model: ModelInfo | undefined, resolution: string | null, aspect: string, seconds: number | null): number | null {
  const res = resolution ?? defaultResolution(model);
  const rate = res ? model?.usd_per_second?.[res]?.[aspect] : undefined;
  return rate === undefined || !seconds ? null : Math.round(rate * seconds * 10000) / 10000;
}

/** Cents under a dollar ("32¢"), dollars above; `exact` is for a tooltip. */
export function usdLabel(usd: number): { short: string; exact: string } {
  const exact = `$${usd.toFixed(4)}`;
  return { short: usd < 1 ? `${Math.max(1, Math.round(usd * 100))}¢` : `$${usd.toFixed(2)}`, exact };
}

/** Quality tiers for video: one click = model + resolution (Seedance via OpenRouter). */
export const VIDEO_TIERS = [
  { id: "draft", provider: "openrouter_video", model: "bytedance/seedance-2.0-mini", resolution: "480p" },
  { id: "standard", provider: "openrouter_video", model: "bytedance/seedance-2.0-mini", resolution: "720p" },
  { id: "publish", provider: "openrouter_video", model: "bytedance/seedance-2.5-flash", resolution: "720p" },
  { id: "premium", provider: "openrouter_video", model: "bytedance/seedance-2.5", resolution: "1080p" },
] as const;
export type TierId = (typeof VIDEO_TIERS)[number]["id"];

export function activeTier(providerId: string | undefined, modelId: string | undefined, resolution: string | null): TierId | null {
  return VIDEO_TIERS.find((t) => t.provider === providerId && t.model === modelId && t.resolution === resolution)?.id ?? null;
}
