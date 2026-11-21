// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import {
  MAX_SCENES,
  addScene,
  canSubmitStory,
  isStoryFinished,
  removeScene,
  storyCapable,
  storyPrice,
  storyProgress,
  storySeconds,
  storyTitle,
  trimScenes,
} from "./stories";
import type { Job, JobStatus, ModelInfo, Story, StoryStatus } from "./types";

const model = (over: Partial<ModelInfo> = {}): ModelInfo => ({
  id: "m",
  label: "M",
  kind: "video",
  license: "",
  commercial_use: "yes",
  aspect_ratios: ["16:9"],
  credit_cost: 5,
  max_count: 1,
  durations: [5, 3],
  accepts_image: false,
  requires_image: false,
  upscale_targets: [],
  upscale_credits: {},
  ...over,
});

const job = (status: JobStatus): Job =>
  ({ id: status, status, params: { duration: 5 }, assets: [] }) as unknown as Job;

const story = (statuses: JobStatus[], status: StoryStatus = "pending", title: string | null = null): Story => ({
  id: "s",
  title,
  status,
  error: null,
  created_at: "2026-11-21T00:00:00Z",
  finished_at: null,
  cost: 0,
  final: null,
  scenes: statuses.map((st, index) => ({ index, prompt: `scene ${index + 1}`, job: job(st) })),
});

describe("storyCapable", () => {
  it("needs a text-to-video model with 5 s clips", () => {
    expect(storyCapable(model())).toBe(true);
    expect(storyCapable(model({ durations: [3] }))).toBe(false);
    expect(storyCapable(model({ durations: [5, 10] }))).toBe(true);
    expect(storyCapable(model({ requires_image: true }))).toBe(false);
    expect(storyCapable(model({ kind: "image", durations: [] }))).toBe(false);
    expect(storyCapable(undefined)).toBe(false);
  });
});

describe("storyPrice", () => {
  it("is the sum of the scenes", () => {
    expect(storyPrice(model(), 3)).toEqual({ scenes: 3, each: 5, total: 15 });
    expect(storyPrice(model({ credit_cost: 10 }), 4).total).toBe(40);
    expect(storyPrice(undefined, 3).total).toBe(0);
  });
});

describe("scene prompts", () => {
  it("keeps 2-4 scenes", () => {
    expect(addScene(["a", "b"])).toEqual(["a", "b", ""]);
    expect(addScene(["a", "b", "c", "d"])).toHaveLength(MAX_SCENES);
    expect(removeScene(["a", "b", "c"], 1)).toEqual(["a", "c"]);
    expect(removeScene(["a", "b"], 0)).toEqual(["a", "b"]);
  });
  it("can be submitted only when every scene has text", () => {
    expect(canSubmitStory(["a lantern", "a river"])).toBe(true);
    expect(canSubmitStory(["a lantern", "  "])).toBe(false);
    expect(canSubmitStory(["ab", "a river"])).toBe(false);
    expect(canSubmitStory(["a lantern"])).toBe(false);
    expect(canSubmitStory(["one one", "two two", "three", "four!", "fifth"])).toBe(false);
  });
  it("trims what is sent", () => {
    expect(trimScenes(["  a lantern ", "river\n"])).toEqual(["a lantern", "river"]);
  });
});

describe("storyProgress", () => {
  it("counts finished scenes and leaves room for joining", () => {
    expect(storyProgress(story(["done", "running", "queued"]))).toMatchObject({ done: 1, failed: 0, active: 2, total: 3, percent: 30 });
    expect(storyProgress(story(["done", "done", "done"], "stitching")).percent).toBe(95);
    expect(storyProgress(story(["done", "done", "done"], "ready")).percent).toBe(100);
    expect(storyProgress(story(["done", "failed"], "partial"))).toMatchObject({ done: 1, failed: 1, active: 0 });
  });
});

describe("story helpers", () => {
  it("knows when polling can stop", () => {
    expect(isStoryFinished(story([], "pending"))).toBe(false);
    expect(isStoryFinished(story([], "stitching"))).toBe(false);
    for (const s of ["ready", "partial", "failed"] as const) expect(isStoryFinished(story([], s))).toBe(true);
  });
  it("titles by name, else first scene", () => {
    expect(storyTitle(story(["done"], "ready", " My film "))).toBe("My film");
    expect(storyTitle(story(["done", "done"]))).toBe("scene 1");
  });
  it("adds up the seconds", () => {
    expect(storySeconds(story(["done", "done", "done"]))).toBe(15);
  });
});
