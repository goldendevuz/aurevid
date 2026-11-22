// SPDX-License-Identifier: AGPL-3.0-or-later
// Request/response shapes for POST /api/prompt/expand (see backend/app/routers/prompt.py).

export interface ExpandRequest {
  prompt: string;
  kind: "video" | "image";
  duration_sec?: number;
  aspect_ratio?: string;
  has_audio?: boolean;
}

export interface ExpandResponse {
  prompt: string;
  cost_usd: number | null;
}

/** Builds the request body; video-only fields are left out for images. */
export function buildExpandRequest(opts: {
  prompt: string;
  kind: "video" | "image";
  durationSec?: number | null;
  aspect?: string | null;
  hasAudio?: boolean;
}): ExpandRequest {
  const body: ExpandRequest = { prompt: opts.prompt.trim(), kind: opts.kind };
  if (opts.aspect && /^\d{1,2}:\d{1,2}$/.test(opts.aspect)) body.aspect_ratio = opts.aspect;
  if (opts.kind === "video") {
    if (opts.durationSec && opts.durationSec > 0) body.duration_sec = Math.min(60, Math.round(opts.durationSec));
    body.has_audio = Boolean(opts.hasAudio);
  }
  return body;
}

/** Returns the expanded text, or null when the response is unusable. */
export function readExpandedPrompt(res: Partial<ExpandResponse> | null | undefined): string | null {
  const text = typeof res?.prompt === "string" ? res.prompt.trim() : "";
  return text || null;
}
