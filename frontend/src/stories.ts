// SPDX-License-Identifier: AGPL-3.0-or-later
// Multi-scene video: pure helpers (limits, price, progress) and polling of a story.
import { api } from "./api";
import { priceOf } from "./pricing";
import type { ModelInfo, Story } from "./types";

export const STORY_SCENE_SECONDS = 5; // every scene is one 5 s clip (backend services/stories.py)
export const MIN_SCENES = 2;
export const MAX_SCENES = 4;
export const MIN_PROMPT = 3;

/** Text-to-video models that make 5 s clips can be chained into a story. */
export function storyCapable(model: ModelInfo | undefined): boolean {
  return !!model && model.kind === "video" && !model.requires_image && model.durations.includes(STORY_SCENE_SECONDS);
}

export interface StoryPrice {
  scenes: number;
  each: number;
  total: number;
}

/** Same formula the backend charges: one clip per scene, no upscale. */
export function storyPrice(model: ModelInfo | undefined, scenes: number, resolution: string | null = null): StoryPrice {
  const each = priceOf(model, 1, null, resolution).each;
  return { scenes, each, total: each * scenes };
}

export const isStoryFinished = (story: Story) => story.status === "ready" || story.status === "partial" || story.status === "failed";

export function trimScenes(prompts: string[]): string[] {
  return prompts.map((p) => p.trim());
}

/** 2-4 scenes and every one long enough to be sent. */
export function canSubmitStory(prompts: string[]): boolean {
  const scenes = trimScenes(prompts);
  return scenes.length >= MIN_SCENES && scenes.length <= MAX_SCENES && scenes.every((p) => p.length >= MIN_PROMPT);
}

export function addScene(prompts: string[]): string[] {
  return prompts.length >= MAX_SCENES ? prompts : [...prompts, ""];
}

export function removeScene(prompts: string[], index: number): string[] {
  return prompts.length <= MIN_SCENES ? prompts : prompts.filter((_, i) => i !== index);
}

export interface StoryProgress {
  done: number;
  failed: number;
  active: number;
  total: number;
  percent: number; // 0-100; joining counts as the last step
}

export function storyProgress(story: Story): StoryProgress {
  const total = story.scenes.length;
  const done = story.scenes.filter((s) => s.job.status === "done").length;
  const failed = story.scenes.filter((s) => s.job.status === "failed").length;
  const active = total - done - failed;
  if (story.status === "ready") return { done, failed, active, total, percent: 100 };
  // Scenes are worth 90 %; joining the clips is the rest.
  const percent = total === 0 ? 0 : Math.round((done / total) * 90) + (story.status === "stitching" ? 5 : 0);
  return { done, failed, active, total, percent };
}

/** Titles show the story's own name, else the first scene. */
export function storyTitle(story: Story): string {
  return story.title?.trim() || story.scenes[0]?.prompt || "";
}

/** Seconds of video in the finished story. */
export function storySeconds(story: Story): number {
  return story.scenes.reduce((sum, s) => sum + (s.job.params.duration ?? STORY_SCENE_SECONDS), 0);
}

/** Follow a story until it is ready/partial/failed (polling); returns a function that stops. */
export function watchStory(id: string, onUpdate: (story: Story) => void): () => void {
  let closed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const poll = async () => {
    if (closed) return;
    try {
      const story = await api<Story>(`/api/stories/${id}`);
      if (closed) return;
      onUpdate(story);
      if (isStoryFinished(story)) return;
    } catch {
      /* transient */
    }
    timer = setTimeout(() => void poll(), 3000);
  };
  timer = setTimeout(() => void poll(), 1500);
  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
  };
}
