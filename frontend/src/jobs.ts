// SPDX-License-Identifier: AGPL-3.0-or-later
import { api } from "./api";
import type { Job } from "./types";

export const isFinished = (job: Job) => job.status === "done" || job.status === "failed";
export const isUpscaleJob = (job: Job) => job.provider === "local" && !!job.params.upscale;

/** Follow a job until it finishes; returns a function that stops watching. */
export function watchJob(id: string, onUpdate: (job: Job) => void): () => void {
  // Server-Sent Events first; fall back to polling if the stream is unavailable.
  let closed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const poll = async () => {
    if (closed) return;
    try {
      const job = await api<Job>(`/api/jobs/${id}`);
      onUpdate(job);
      if (job.status === "done" || job.status === "failed") return;
    } catch {
      /* transient */
    }
    timer = setTimeout(poll, 3000);
  };
  const es = new EventSource(`/api/jobs/${id}/events`);
  es.addEventListener("job", (e) => {
    const job = JSON.parse((e as MessageEvent).data) as Job;
    onUpdate(job);
    if (job.status === "done" || job.status === "failed") es.close();
  });
  es.onerror = () => {
    es.close();
    void poll();
  };
  return () => {
    closed = true;
    es.close();
    if (timer) clearTimeout(timer);
  };
}

/**
 * Start a new job with exactly the same settings (charged like any new job).
 * A local upscale is retried from its source image; everything else goes through POST /api/jobs,
 * so a model that is no longer offered fails with the usual readable error.
 */
export function retryJob(job: Job): Promise<Job> {
  const p = job.params;
  if (isUpscaleJob(job) && p.source_asset_id) {
    return api<Job>(`/api/assets/${p.source_asset_id}/upscale`, { method: "POST", body: { target: p.upscale } });
  }
  const video = job.kind === "video";
  return api<Job>("/api/jobs", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: {
      prompt: job.prompt,
      provider: job.provider,
      model: job.model,
      aspect_ratio: p.aspect_ratio,
      ...(p.size ? { size: p.size } : {}),
      count: video ? 1 : Math.max(1, job.count),
      preset_id: job.preset_id,
      seed: p.seed ?? null,
      duration: video ? (p.duration ?? null) : null,
      image_asset_id: p.image_asset_id ?? null,
      upscale: p.upscale ?? null,
      ...(p.resolution ? { resolution: p.resolution } : {}),
      ...(p.quality ? { quality: p.quality } : {}),
    },
  });
}
