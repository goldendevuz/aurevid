// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ModelInfo } from "./types";

export interface DirectorBeat {
  timeRange: string;
  name: string;
  text: string;
}

export interface DirectorPlan {
  openingFrame: string;
  beats: DirectorBeat[];
  look: string;
  audio?: string;
}

/**
 * Parses structured expansion text returned from `/api/prompt/expand`.
 * Example format:
 * Opening frame: An astronaut standing on a red Martian dune.
 * Beat 1 (0-5 s) - The Arrival: He looks up at two moons in the twilight sky.
 * Beat 2 (5-10 s) - Discovery: A holographic signal pulses from the canyon below.
 * Look: 35mm anamorphic lens, warm golden hour tones, subtle dust particles.
 * Audio: Low synth drone with gentle wind whistling through the helmet.
 */
export function parseDirectorPlan(text: string): DirectorPlan {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  let openingFrame = "";
  let look = "";
  let audio: string | undefined = undefined;
  const beats: DirectorBeat[] = [];

  for (const line of lines) {
    if (/^opening frame:\s*/i.test(line)) {
      openingFrame = line.replace(/^opening frame:\s*/i, "").trim();
      continue;
    }
    if (/^look:\s*/i.test(line)) {
      look = line.replace(/^look:\s*/i, "").trim();
      continue;
    }
    if (/^audio:\s*/i.test(line)) {
      audio = line.replace(/^audio:\s*/i, "").trim();
      continue;
    }

    // Match beats like: Beat 1 (0-5 s) - Name: Description
    // or Beat 1 (0-5 s): Description
    const beatMatch = line.match(/^beat\s+\d+\s*\(([^)]+)\)\s*[-:]?\s*(?:([^:]+):)?\s*(.*)$/i);
    if (beatMatch) {
      const timeRange = beatMatch[1]?.trim() || "";
      const name = beatMatch[2]?.trim() || `Scene ${beats.length + 1}`;
      const beatText = (beatMatch[3] || line).trim();
      beats.push({ timeRange, name, text: beatText });
    }
  }

  // Fallback if formatting was non-standard:
  if (!openingFrame && lines.length > 0) {
    openingFrame = lines[0];
  }
  if (beats.length === 0) {
    beats.push({ timeRange: "0-5 s", name: "Main Scene", text: openingFrame || text });
  }

  return { openingFrame, beats, look, audio };
}

/**
 * Re-assembles an edited DirectorPlan into a single coherent prompt string.
 */
export function formatDirectorPrompt(plan: DirectorPlan): string {
  const parts: string[] = [];
  if (plan.openingFrame) {
    parts.push(`Opening frame: ${plan.openingFrame}`);
  }
  plan.beats.forEach((b, idx) => {
    parts.push(`Beat ${idx + 1} (${b.timeRange}) - ${b.name}: ${b.text}`);
  });
  if (plan.look) {
    parts.push(`Look: ${plan.look}`);
  }
  if (plan.audio) {
    parts.push(`Audio: ${plan.audio}`);
  }
  return parts.join("\n");
}

/**
 * Decides whether a requested duration should produce a single clip job or a multi-scene story.
 */
export function shouldUseStory(durationSec: number, model?: ModelInfo | null): boolean {
  if (!model) return durationSec > 10;
  const maxModelClip = model.durations?.length ? Math.max(...model.durations) : 5;
  return durationSec > maxModelClip;
}

/**
 * Converts a plan's beats into individual scene prompts for a multi-scene Story.
 */
export function directorToStoryScenes(plan: DirectorPlan): string[] {
  if (plan.beats.length === 0) {
    return [plan.openingFrame || "Scene"];
  }
  return plan.beats.map((b) => {
    let p = `${b.name}: ${b.text}`;
    if (plan.look) p += ` (${plan.look})`;
    return p;
  });
}

export interface BuildDirectorJobPayloadOptions {
  plan: DirectorPlan;
  providerId: string;
  modelId: string;
  aspectRatio: string;
  size?: string;
  duration: number;
  resolution?: string | null;
  startImageAssetId?: string | null;
}

export function buildDirectorJobPayload(options: BuildDirectorJobPayloadOptions) {
  return {
    prompt: formatDirectorPrompt(options.plan),
    provider: options.providerId,
    model: options.modelId,
    aspect_ratio: options.aspectRatio,
    size: options.size || "large",
    count: 1,
    duration: options.duration,
    image_asset_id: options.startImageAssetId || null,
    ...(options.resolution ? { resolution: options.resolution } : {}),
  };
}

export interface BuildDirectorStoryPayloadOptions {
  plan: DirectorPlan;
  providerId: string;
  modelId: string;
  aspectRatio: string;
  size?: string;
  resolution?: string | null;
}

export function buildDirectorStoryPayload(options: BuildDirectorStoryPayloadOptions) {
  return {
    provider: options.providerId,
    model: options.modelId,
    aspect_ratio: options.aspectRatio,
    size: options.size || "large",
    scenes: directorToStoryScenes(options.plan),
    ...(options.resolution ? { resolution: options.resolution } : {}),
  };
}
