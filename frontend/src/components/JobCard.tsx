// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Asset, Job } from "../types";
import { Icon, type IconName } from "./icons";
import { Badge, Button, ErrorText, inputClass } from "./ui";

const REASONS = ["illegal", "sexual", "minor_safety", "violence", "copyright", "other"] as const;

function ReportForm({ asset, onClose }: { asset: Asset; onClose: () => void }) {
  const { t } = useTranslation();
  const [reason, setReason] = useState<(typeof REASONS)[number]>("other");
  const [details, setDetails] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (sent) return <p className="text-xs text-ok">{t("report.thanks")}</p>;
  return (
    <form
      className="mt-2 space-y-2 rounded-xl border border-line bg-bg/80 p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        try {
          await api("/api/reports", {
            method: "POST",
            body: { asset_id: asset.id, reason, details: details || null },
          });
          setSent(true);
        } catch (err) {
          setError(err);
        }
      }}
    >
      <p className="text-xs font-semibold">{t("report.title")}</p>
      <select value={reason} onChange={(e) => setReason(e.target.value as typeof reason)} className={inputClass}>
        {REASONS.map((r) => (
          <option key={r} value={r}>{t(`report.reason_${r}`)}</option>
        ))}
      </select>
      <textarea
        value={details}
        maxLength={500}
        onChange={(e) => setDetails(e.target.value)}
        placeholder={t("report.details")}
        className={inputClass}
        rows={2}
      />
      <div className="flex gap-2">
        <Button type="submit" variant="danger">{t("report.submit")}</Button>
        <Button type="button" variant="ghost" onClick={onClose}>{t("report.cancel")}</Button>
      </div>
      <ErrorText error={error} />
    </form>
  );
}

/** Whole seconds since `since`, ticking once a second while `active`. */
function useElapsed(since: string | null | undefined, active: boolean): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  if (!active || !since) return null;
  const start = Date.parse(since);
  return Number.isNaN(start) ? null : Math.max(0, Math.floor((now - start) / 1000));
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function ActionButton({
  icon,
  label,
  onClick,
  href,
  download,
  active,
  tone,
}: {
  icon: IconName;
  label: string;
  onClick?: () => void;
  href?: string;
  download?: boolean;
  active?: boolean;
  tone?: "danger";
}) {
  const cls = `grid h-8 w-8 place-items-center rounded-lg bg-black/55 backdrop-blur transition hover:bg-black/75 ${
    active ? "text-accent-3" : tone === "danger" ? "text-ink hover:text-danger" : "text-ink hover:text-accent"
  }`;
  const glyph = <Icon name={icon} size={16} fill={active ? "currentColor" : "none"} />;
  return href ? (
    <a href={href} download={download || undefined} target={download ? undefined : "_blank"} rel="noopener" className={cls} aria-label={label} title={label}>
      {glyph}
    </a>
  ) : (
    <button type="button" onClick={onClick} className={cls} aria-label={label} title={label} aria-pressed={active}>
      {glyph}
    </button>
  );
}

export default function JobCard({
  job,
  onChange,
  onReuse,
  onAnimate,
  onUpscale,
}: {
  job: Job;
  onChange: (job: Job) => void;
  onReuse?: (prompt: string) => void;
  onAnimate?: (asset: Asset) => void;
  onUpscale?: (asset: Asset, target: "4k" | "8k") => void;
}) {
  const { t } = useTranslation();
  const [reporting, setReporting] = useState<string | null>(null);
  const tone = job.status === "done" ? "ok" : job.status === "failed" ? "danger" : "muted";
  const pending = job.status === "queued" || job.status === "running";
  const ratio = job.params.width && job.params.height ? job.params.width / job.params.height : 1;
  const isVideo = job.kind === "video";
  const elapsed = useElapsed(job.started_at, job.status === "running");
  const typical = job.typical_seconds ?? null;
  const slow = elapsed !== null && typical !== null && elapsed > typical * 1.5;
  const human = (s: number) => (s < 90 ? t("studio.seconds", { count: s }) : t("job.minutes", { count: Math.round(s / 60) }));

  const toggleFavorite = async (asset: Asset) => {
    const updated = await api<Asset>(`/api/assets/${asset.id}/favorite`, {
      method: "POST",
      body: { favorite: !asset.is_favorite },
    });
    onChange({ ...job, assets: job.assets.map((a) => (a.id === asset.id ? updated : a)) });
  };
  const remove = async (asset: Asset) => {
    await api(`/api/assets/${asset.id}`, { method: "DELETE" });
    onChange({ ...job, assets: job.assets.filter((a) => a.id !== asset.id) });
  };

  const isUpscaleJob = job.provider === "local" && job.params.upscale;
  const title = isUpscaleJob ? t("job.upscaleTo", { target: job.params.upscale!.toUpperCase() }) : job.prompt;

  return (
    <article className="glass rise overflow-hidden rounded-[var(--radius-card)]">
      {pending && (
        <div className={`grid gap-1 p-1 ${isVideo || job.count === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
          {Array.from({ length: isVideo ? 1 : job.count }).map((_, i) => (
            <div key={i} className="shimmer relative grid place-items-center rounded-xl" style={{ aspectRatio: ratio }}>
              <span className="flex items-center gap-2 rounded-full bg-black/50 px-3 py-1 text-[11px] font-medium text-ink backdrop-blur">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                {t(`job.${job.status}`)}
              </span>
            </div>
          ))}
        </div>
      )}
      {job.assets.length > 0 && (
        <div className={`grid gap-1 p-1 ${isVideo || job.assets.length === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
          {job.assets.map((a) => {
            const video = a.mime.startsWith("video/");
            const big = Math.max(a.width, a.height);
            return (
              <figure key={a.id} className="group relative overflow-hidden rounded-xl bg-raised">
                {video ? (
                  <video
                    src={a.url}
                    controls
                    loop
                    muted
                    playsInline
                    preload="metadata"
                    aria-label={job.prompt}
                    className="h-auto w-full"
                    style={{ aspectRatio: a.width && a.height ? a.width / a.height : undefined }}
                  />
                ) : (
                  <a href={a.url} target="_blank" rel="noopener" title={t("job.open")}>
                    <img
                      src={a.preview_url || a.url}
                      alt={job.prompt}
                      loading="lazy"
                      width={a.width}
                      height={a.height}
                      className="h-auto w-full transition duration-500 group-hover:scale-[1.02]"
                    />
                  </a>
                )}
                <span className="pointer-events-none absolute left-2 top-2 rounded-md bg-black/55 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-ink backdrop-blur">
                  {a.width}×{a.height}
                  {big >= 7680 ? " · 8K" : big >= 3840 ? " · 4K" : ""}
                </span>
                <div
                  className={`absolute inset-x-0 ${video ? "bottom-11" : "bottom-0"} flex items-end justify-between gap-1 bg-gradient-to-t from-black/70 to-transparent p-2 opacity-0 transition group-focus-within:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100 ${
                    video ? "pointer-events-none [&>*]:pointer-events-auto" : ""
                  } ${video ? "bottom-10" : ""}`}
                >
                  <div className="flex gap-1">
                    <ActionButton
                      icon="star"
                      active={a.is_favorite}
                      label={a.is_favorite ? t("job.unfavorite") : t("job.favorite")}
                      onClick={() => void toggleFavorite(a)}
                    />
                    {onAnimate && !video && (
                      <ActionButton icon="video" label={t("job.animate")} onClick={() => onAnimate(a)} />
                    )}
                    {onUpscale &&
                      !video &&
                      (["4k", "8k"] as const)
                        .filter((target) => big < (target === "4k" ? 3840 : 7680))
                        .map((target) => (
                          <button
                            key={target}
                            type="button"
                            onClick={() => onUpscale(a, target)}
                            title={t("job.upscaleTo", { target: target.toUpperCase() })}
                            aria-label={t("job.upscaleTo", { target: target.toUpperCase() })}
                            className="h-8 rounded-lg bg-black/55 px-2 text-[11px] font-bold text-ink backdrop-blur transition hover:bg-black/75 hover:text-accent"
                          >
                            {target.toUpperCase()}
                          </button>
                        ))}
                  </div>
                  <div className="flex gap-1">
                    <ActionButton icon="download" href={a.url} download label={t("job.download")} />
                    <ActionButton icon="flag" label={t("job.report")} onClick={() => setReporting(reporting === a.id ? null : a.id)} />
                    <ActionButton icon="trash" tone="danger" label={t("job.delete")} onClick={() => void remove(a)} />
                  </div>
                </div>
                {reporting === a.id && (
                  <div className="p-2">
                    <ReportForm asset={a} onClose={() => setReporting(null)} />
                  </div>
                )}
              </figure>
            );
          })}
        </div>
      )}
      <div className="px-4 pb-4 pt-3">
        <div className="flex items-start justify-between gap-3">
          <p className="line-clamp-2 text-sm leading-snug text-ink">{title}</p>
          <Badge tone={tone}>{t(`job.${job.status}`)}</Badge>
        </div>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-1.5 text-[11px] text-muted">
          <Icon name={isVideo ? "video" : "image"} size={12} />
          <span>{job.provider}</span>·<span>{job.params.aspect_ratio}</span>·
          <span>{isVideo ? t("studio.seconds", { count: job.params.duration ?? 0 }) : `${job.count}×`}</span>
          {job.preset_id && (
            <>
              ·<span>{t(`presets.${job.preset_id}.name`, { defaultValue: job.preset_id })}</span>
            </>
          )}
        </p>
        {elapsed !== null && (
          <div className="mt-3" role="status">
            <div className="flex items-center justify-between gap-2 text-[11px] tabular-nums">
              <span className="font-medium text-ink">{t("job.elapsed", { time: clock(elapsed) })}</span>
              {typical !== null && <span className="text-muted">{t("job.usually", { time: human(typical) })}</span>}
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-raised">
              <div
                className={`h-full rounded-full transition-[width] duration-1000 ease-linear ${slow ? "animate-pulse" : ""}`}
                style={{
                  width: `${typical ? Math.min(95, Math.max(4, (elapsed / typical) * 100)) : 30}%`,
                  background: "var(--aurora)",
                }}
              />
            </div>
            {slow && <p className="mt-2 text-[11px] text-muted">{t("job.slow")}</p>}
          </div>
        )}
        {job.status === "queued" && job.queue_position ? (
          <p className="mt-2 text-[11px] font-medium text-accent">
            {t("job.queuePosition", {
              position: job.queue_position,
              minutes: Math.max(1, Math.ceil((job.eta_seconds ?? 0) / 60)),
            })}
          </p>
        ) : null}
        {job.status === "failed" && (
          <p className="mt-2 text-xs text-danger">
            {job.error} {t("job.refunded")}
          </p>
        )}
        {job.status === "done" && job.error && <p className="mt-2 text-xs text-accent-3">{t("job.partial")}</p>}
        {onReuse && !isUpscaleJob && (
          <button
            type="button"
            onClick={() => onReuse(job.prompt)}
            className="mt-2.5 inline-flex items-center gap-1.5 text-[11px] font-medium text-muted transition hover:text-accent"
          >
            <Icon name="copy" size={12} />
            {t("job.copyPrompt")}
          </button>
        )}
      </div>
    </article>
  );
}
