// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { isDraft } from "../quality";
import { storyProgress, storySeconds, storyTitle } from "../stories";
import type { Scene, Story } from "../types";
import { Icon } from "./icons";
import { Badge, Button, ErrorText } from "./ui";

interface Handlers {
  /** Run a failed scene again (charged like a new clip). Throws ApiError on failure. */
  onRetryScene: (story: Story, index: number) => Promise<void>;
  /** Join the clips again after a failed join (free). */
  onRestitch: (story: Story) => Promise<void>;
  onDelete: (story: Story) => Promise<void>;
}

const TONE = { pending: "muted", stitching: "muted", ready: "live", partial: "danger", failed: "danger" } as const;

function SceneTile({ scene, busy, onRetry }: { scene: Scene; busy: boolean; onRetry: () => void }) {
  const { t } = useTranslation();
  const { job } = scene;
  const asset = job.assets[0];
  const pending = job.status === "queued" || job.status === "running";
  return (
    <li className="min-w-0 overflow-hidden rounded-xl border border-line bg-bg/60">
      <div className="relative grid aspect-video place-items-center bg-black/30">
        {asset ? (
          // "#t=0.1" makes the browser paint the first frame as a poster.
          <video src={`${asset.url}#t=0.1`} muted playsInline preload="metadata" className="h-full w-full object-cover" aria-label={t("story.scene", { n: scene.index + 1 })} />
        ) : pending ? (
          <span className="shimmer absolute inset-0" aria-hidden />
        ) : null}
        <span className="absolute left-1.5 top-1.5 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-ink backdrop-blur">{scene.index + 1}</span>
        {!asset && (
          <span className="relative flex items-center gap-1.5 rounded-full bg-black/55 px-2.5 py-1 text-[11px] font-medium text-ink backdrop-blur">
            {pending && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />}
            {t(`job.${job.status}`)}
          </span>
        )}
      </div>
      <div className="p-2">
        <p className="line-clamp-2 text-[11px] leading-snug text-ink/90" title={scene.prompt}>{scene.prompt}</p>
        {job.status === "failed" && (
          <div className="mt-1.5 space-y-1.5">
            <p className="text-[11px] text-danger">{t("story.sceneFailed")}</p>
            <Button size="sm" variant="ghost" disabled={busy} onClick={onRetry}>
              <Icon name="retry" size={13} />
              {busy ? t("story.retrying") : t("story.retryScene")}
            </Button>
          </div>
        )}
      </div>
    </li>
  );
}

/**
 * A multi-scene video: per-scene thumbnails and status, overall progress, the joined video when
 * ready, retry for failed scenes, download and delete. Presents server state only.
 */
export default function StoryCard({ story, index = 0, ...handlers }: Handlers & { story: Story; index?: number }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const progress = storyProgress(story);
  const working = story.status === "pending" || story.status === "stitching";
  const first = story.scenes[0]?.job;
  const ratio = first?.params.width && first.params.height ? first.params.width / first.params.height : 16 / 9;
  const style = { "--i": Math.min(index, 12) } as React.CSSProperties;

  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  return (
    <article className="rise glass rounded-[var(--radius-card)] p-3 sm:p-4" style={style} aria-label={t("story.title")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
            <Icon name="layers" size={13} />
            {t("story.title")}
          </p>
          <p className="mt-1 line-clamp-2 text-sm text-ink" title={storyTitle(story)}>{storyTitle(story)}</p>
        </div>
        <Badge tone={TONE[story.status]}>{t(`story.status_${story.status}`)}</Badge>
      </div>

      {working && (
        <div className="mt-3" role="status">
          <div className="h-1.5 overflow-hidden rounded-full bg-black/40">
            <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.max(4, progress.percent)}%`, background: "var(--aurora)" }} />
          </div>
          <p className="mt-1.5 text-[11px] text-muted">
            {story.status === "stitching" ? t("story.stitching") : t("story.progress", { done: progress.done, total: progress.total })}
          </p>
        </div>
      )}

      {story.status === "ready" && story.final && (
        <div className="mt-3">
          <video
            src={`${story.final.url}#t=0.1`}
            controls
            playsInline
            preload="metadata"
            className="block h-auto max-h-[60vh] w-full rounded-2xl bg-black"
            style={{ aspectRatio: story.final.width && story.final.height ? story.final.width / story.final.height : ratio }}
            aria-label={t("story.final")}
          />
          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 text-[11px] tabular-nums text-muted">
            <span>{story.final.width}×{story.final.height}</span>
            {isDraft(story.final.mime, story.final.width, story.final.height) && (
              <span className="rounded-full bg-accent-3/15 px-2 py-0.5 font-semibold text-accent-3" title={t("job.draftTitle")}>{t("job.draft")}</span>
            )}
            <span>{t("story.duration", { count: storySeconds(story) })} · {t("price.selection", { count: story.cost })}</span>
          </p>
        </div>
      )}

      {story.status === "partial" && <p role="status" className="mt-3 text-xs text-accent-3">{t("story.partialHint")}</p>}
      {story.status === "failed" && story.error && <p role="alert" className="mt-3 text-xs text-danger">{t(`errors.${story.error}`, { defaultValue: t("errors.generic") })}</p>}

      <ul className={`mt-3 grid gap-2 ${story.scenes.length > 2 ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2"} ${story.scenes.length === 4 ? "sm:grid-cols-4" : ""}`} aria-label={t("story.scenes")}>
        {story.scenes.map((scene) => (
          <SceneTile
            key={scene.index}
            scene={scene}
            busy={busy === `scene-${scene.index}`}
            onRetry={() => void run(`scene-${scene.index}`, () => handlers.onRetryScene(story, scene.index))}
          />
        ))}
      </ul>

      {!working && (
        <div className="mt-3 flex flex-wrap gap-2">
          {story.status === "ready" && story.final && (
            <a
              href={story.final.url}
              download
              className="inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-1.5 text-xs font-medium text-ink transition hover:bg-white/[0.06]"
            >
              <Icon name="download" size={14} />
              {t("story.download")}
            </a>
          )}
          {story.status === "failed" && story.error === "stitch_failed" && (
            <Button size="sm" disabled={busy !== null} onClick={() => void run("stitch", () => handlers.onRestitch(story))}>
              <Icon name="retry" size={14} />
              {busy === "stitch" ? t("story.retrying") : t("story.restitch")}
            </Button>
          )}
          <Button
            size="sm"
            variant="danger"
            disabled={busy !== null}
            onClick={() => {
              if (window.confirm(t("story.deleteConfirm"))) void run("delete", () => handlers.onDelete(story));
            }}
          >
            <Icon name="trash" size={14} />
            {t("story.delete")}
          </Button>
        </div>
      )}
      <ErrorText error={error} />
    </article>
  );
}
