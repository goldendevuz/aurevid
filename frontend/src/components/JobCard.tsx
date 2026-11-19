// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { isUpscaleJob as isUpscale } from "../jobs";
import type { Asset, Job } from "../types";
import { Icon } from "./icons";
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

function Chips({ job }: { job: Job }) {
  const { t } = useTranslation();
  const isVideo = job.kind === "video";
  const isUpscaleJob = job.provider === "local" && job.params.upscale;
  const chip = "rounded-md bg-raised px-1.5 py-0.5";
  return (
    <ul className="flex flex-wrap gap-1.5 text-[11px] text-muted" aria-label={t("job.details")}>
      <li className="flex items-center gap-1 rounded-md bg-raised px-1.5 py-0.5 font-medium text-ink/90" title={job.provider_name ?? job.provider}>
        <Icon name={isVideo ? "video" : "image"} size={12} />
        {job.model_label ?? job.model.split("/").pop()}
      </li>
      {job.provider_name && <li className={chip}>{job.provider_name}</li>}
      <li className={chip}>{job.params.aspect_ratio}</li>
      {job.params.size && !isUpscaleJob && <li className={chip}>{t(`studio.size_${job.params.size}`, { defaultValue: job.params.size })}</li>}
      {isVideo ? <li className={chip}>{t("studio.seconds", { count: job.params.duration ?? 0 })}</li> : <li className={chip}>{job.count}×</li>}
      {job.params.upscale && !isUpscaleJob && <li className={`${chip} font-semibold text-accent`}>{job.params.upscale.toUpperCase()}</li>}
      {job.has_audio && (
        <li className={`${chip} flex items-center gap-1 text-accent`}>
          <Icon name="sound" size={12} />
          {t("studio.withAudio")}
        </li>
      )}
      {job.preset_id && (
        <li className={`${chip} flex items-center gap-1`}>
          <Icon name="camera" size={12} />
          {t(`presets.${job.preset_id}.name`, { defaultValue: job.preset_id })}
        </li>
      )}
      <li className={`${chip} tabular-nums`}>{new Date(job.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</li>
    </ul>
  );
}

interface Handlers {
  onChange: (job: Job) => void;
  /** Start a new job with the same settings (failed jobs). Throws ApiError on failure. */
  onRetry?: (job: Job) => Promise<void>;
  /** Remove the whole finished job and its files. Throws ApiError on failure. */
  onDelete?: (job: Job) => Promise<void>;
  onRemix?: (job: Job) => void;
  onAnimate?: (asset: Asset) => void;
  onUpscale?: (asset: Asset, target: "4k" | "8k") => void;
}

/** Full-size viewer: the media on the left, every detail and action on the right (Remix restores all settings). */
function JobDialog({ job, onClose, onChange, onRemix, onAnimate, onUpscale }: Handlers & { job: Job; onClose: () => void }) {
  const { t } = useTranslation();
  const [idx, setIdx] = useState(0);
  const [reporting, setReporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const assets = job.assets;
  const a = assets[Math.min(idx, assets.length - 1)];
  const isUpscaleJob = job.provider === "local" && job.params.upscale;

  useEffect(() => {
    closeRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") setIdx((i) => Math.min(i + 1, Math.max(0, assets.length - 1)));
      if (e.key === "ArrowLeft") setIdx((i) => Math.max(i - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose, assets.length]);

  useEffect(() => {
    if (assets.length === 0) onClose();
  }, [assets.length, onClose]);
  if (!a) return null;

  const video = a.mime.startsWith("video/");
  const big = Math.max(a.width, a.height);
  const act = "inline-flex items-center justify-center gap-2 rounded-xl border border-line bg-raised/50 px-3 py-2 text-xs font-medium text-ink transition hover:border-white/25 hover:bg-raised";

  const toggleFavorite = async () => {
    const updated = await api<Asset>(`/api/assets/${a.id}/favorite`, { method: "POST", body: { favorite: !a.is_favorite } });
    onChange({ ...job, assets: assets.map((x) => (x.id === a.id ? updated : x)) });
  };
  const remove = async () => {
    await api(`/api/assets/${a.id}`, { method: "DELETE" });
    setIdx(0);
    onChange({ ...job, assets: assets.filter((x) => x.id !== a.id) });
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(job.prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className="fade fixed inset-0 z-50 flex items-stretch justify-center bg-black/80 p-0 backdrop-blur-md sm:p-6" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={job.prompt} className="pop glass relative grid max-h-full w-full max-w-6xl overflow-hidden rounded-none sm:rounded-[28px] md:grid-cols-[minmax(0,1fr)_360px]">
        <button ref={closeRef} type="button" onClick={onClose} aria-label={t("job.close")} title={t("job.close")} className="absolute right-3 top-3 z-10 grid h-9 w-9 place-items-center rounded-full bg-black/60 text-ink backdrop-blur transition hover:bg-black/80 hover:text-accent">
          <span aria-hidden className="text-lg leading-none">×</span>
        </button>

        <div className="flex min-h-0 flex-col items-center justify-center gap-3 overflow-auto bg-black/40 p-3 sm:p-5">
          {video ? (
            <video key={a.id} src={a.url} controls autoPlay loop playsInline className="max-h-[70vh] w-auto max-w-full rounded-2xl" style={{ aspectRatio: a.width && a.height ? a.width / a.height : undefined }} />
          ) : (
            <img key={a.id} src={a.url} alt={job.prompt} width={a.width} height={a.height} className="max-h-[75vh] w-auto max-w-full rounded-2xl object-contain" />
          )}
          {assets.length > 1 && (
            <div className="flex flex-wrap justify-center gap-2" role="tablist">
              {assets.map((x, i) => (
                <button key={x.id} type="button" role="tab" aria-selected={i === idx} onClick={() => setIdx(i)} className={`h-14 w-14 overflow-hidden rounded-xl border-2 transition ${i === idx ? "border-accent" : "border-transparent opacity-60 hover:opacity-100"}`}>
                  {x.mime.startsWith("video/") ? <span className="grid h-full w-full place-items-center bg-raised text-accent"><Icon name="video" size={18} /></span> : <img src={x.preview_url || x.url} alt="" className="h-full w-full object-cover" />}
                </button>
              ))}
            </div>
          )}
        </div>

        <aside className="flex min-h-0 flex-col gap-4 overflow-auto border-t border-white/[0.08] p-5 pt-14 md:border-l md:border-t-0">
          <div>
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">{t("job.prompt")}</p>
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink">{isUpscaleJob ? t("job.upscaleTo", { target: job.params.upscale!.toUpperCase() }) : job.prompt}</p>
            {!isUpscaleJob && (
              <button type="button" onClick={() => void copy()} className="mt-2 inline-flex items-center gap-1.5 text-[11px] font-medium text-muted transition hover:text-accent">
                <Icon name={copied ? "check" : "copy"} size={12} />
                {copied ? t("job.copied") : t("job.copyPrompt")}
              </button>
            )}
          </div>
          <Chips job={job} />
          <p className="text-[11px] tabular-nums text-muted">
            {a.width}×{a.height}
            {big >= 7680 ? " · 8K" : big >= 3840 ? " · 4K" : ""}
          </p>
          {job.status === "done" && job.error && <p className="text-xs text-accent-3">{t("job.partial")}</p>}

          <div className="mt-auto grid grid-cols-2 gap-2">
            {onRemix && !isUpscaleJob && (
              <button type="button" onClick={() => { onRemix(job); onClose(); }} className="btn-aurora col-span-2 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold">
                <Icon name="sparkle" size={16} />
                {t("job.remix")}
              </button>
            )}
            {onAnimate && !video && (
              <button type="button" className={act} onClick={() => { onAnimate(a); onClose(); }}>
                <Icon name="video" size={15} />
                {t("job.animate")}
              </button>
            )}
            <button type="button" className={act} onClick={() => void toggleFavorite()} aria-pressed={a.is_favorite}>
              <Icon name="star" size={15} fill={a.is_favorite ? "currentColor" : "none"} className={a.is_favorite ? "text-accent-2" : ""} />
              {a.is_favorite ? t("job.unfavorite") : t("job.favorite")}
            </button>
            <a className={act} href={a.url} download>
              <Icon name="download" size={15} />
              {t("job.download")}
            </a>
            {onUpscale &&
              !video &&
              (["4k", "8k"] as const)
                .filter((target) => big < (target === "4k" ? 3840 : 7680))
                .map((target) => (
                  <button key={target} type="button" className={act} onClick={() => { onUpscale(a, target); onClose(); }}>
                    <Icon name="wand" size={15} />
                    {t("job.upscaleTo", { target: target.toUpperCase() })}
                  </button>
                ))}
            <button type="button" className={act} onClick={() => setReporting((v) => !v)}>
              <Icon name="flag" size={15} />
              {t("job.report")}
            </button>
            <button type="button" className={`${act} hover:!border-danger/60 hover:!text-danger`} onClick={() => void remove()}>
              <Icon name="trash" size={15} />
              {t("job.delete")}
            </button>
          </div>
          {reporting && <ReportForm asset={a} onClose={() => setReporting(false)} />}
        </aside>
      </div>
    </div>
  );
}

/** A finished job without pictures (failed, or all its files deleted): details, error, Retry and Delete. */
function EmptyJobCard({ job, title, style, onRetry, onDelete, onRemix }: Handlers & { job: Job; title: string; style: React.CSSProperties }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<"retry" | "delete" | null>(null);
  const [error, setError] = useState<unknown>(null);
  const failed = job.status === "failed";
  const run = async (what: "retry" | "delete", fn: (job: Job) => Promise<void>) => {
    if (what === "delete" && !window.confirm(t("job.deleteJobConfirm"))) return;
    setBusy(what);
    setError(null);
    try {
      await fn(job);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };
  return (
    <article className="rise glass rounded-[var(--radius-card)] p-4" style={style}>
      <div className="flex items-start justify-between gap-3">
        <p className="line-clamp-3 text-sm text-ink" title={job.prompt}>{title}</p>
        <Badge tone={failed ? "danger" : "muted"}>{t(`job.${job.status}`)}</Badge>
      </div>
      <div className="mt-3">
        <Chips job={job} />
      </div>
      {failed && (
        <p className="mt-3 text-xs text-danger">
          {job.error && <span className="break-words">{job.error} </span>}
          {job.cost > 0 && t("job.refunded")}
        </p>
      )}
      {!failed && <p className="mt-3 text-xs text-muted">{t("job.noFiles")}</p>}
      {(onRetry || onDelete || onRemix) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {onRetry && failed && (
            <Button size="sm" disabled={busy !== null} onClick={() => void run("retry", onRetry)}>
              <Icon name="retry" size={14} />
              {busy === "retry" ? t("job.retrying") : t("job.retry")}
            </Button>
          )}
          {onRemix && !isUpscale(job) && (
            <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => onRemix(job)}>
              <Icon name="sparkle" size={14} />
              {t("job.remix")}
            </Button>
          )}
          {onDelete && (
            <Button size="sm" variant="danger" disabled={busy !== null} onClick={() => void run("delete", onDelete)}>
              <Icon name="trash" size={14} />
              {t("job.delete")}
            </Button>
          )}
        </div>
      )}
      <ErrorText error={error} />
    </article>
  );
}

export default function JobCard({ job, index = 0, ...handlers }: Handlers & { job: Job; index?: number }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const closeDialog = useCallback(() => setOpen(false), []);
  const pending = job.status === "queued" || job.status === "running";
  const ratio = job.params.width && job.params.height ? job.params.width / job.params.height : 1;
  const isUpscaleJob = job.provider === "local" && job.params.upscale;
  const elapsed = useElapsed(job.started_at, job.status === "running");
  const typical = job.typical_seconds ?? null;
  const slow = elapsed !== null && typical !== null && elapsed > typical * 1.5;
  const human = (s: number) => (s < 90 ? t("studio.seconds", { count: s }) : t("job.minutes", { count: Math.round(s / 60) }));
  const first = job.assets[0];
  const video = first?.mime.startsWith("video/");
  const big = first ? Math.max(first.width, first.height) : 0;
  const title = isUpscaleJob ? t("job.upscaleTo", { target: job.params.upscale!.toUpperCase() }) : job.prompt;
  const style = { "--i": Math.min(index, 12) } as React.CSSProperties;

  const toggleFavorite = async () => {
    if (!first) return;
    const updated = await api<Asset>(`/api/assets/${first.id}/favorite`, { method: "POST", body: { favorite: !first.is_favorite } });
    handlers.onChange({ ...job, assets: job.assets.map((x) => (x.id === first.id ? updated : x)) });
  };
  const quick = "grid h-8 w-8 place-items-center rounded-full bg-black/60 text-ink backdrop-blur transition hover:bg-black/80 hover:text-accent";

  if (pending) {
    return (
      <article className="rise glass overflow-hidden rounded-[var(--radius-card)]" style={style}>
        <div className="shimmer relative grid place-items-center" style={{ aspectRatio: ratio }}>
          <div className="flex flex-col items-center gap-3 px-4 text-center">
            <span className="flex items-center gap-2 rounded-full bg-black/55 px-3 py-1 text-[11px] font-medium text-ink backdrop-blur">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
              {t(`job.${job.status}`)}
              {elapsed !== null && <span className="tabular-nums text-muted">· {clock(elapsed)}</span>}
            </span>
            <p className="line-clamp-3 max-w-[16rem] text-xs text-ink/80">{title}</p>
          </div>
          {elapsed !== null && (
            <div className="absolute inset-x-4 bottom-4" role="status">
              <div className="h-1 overflow-hidden rounded-full bg-black/40">
                <div
                  className={`h-full rounded-full transition-[width] duration-1000 ease-linear ${slow ? "animate-pulse" : ""}`}
                  style={{ width: `${typical ? Math.min(95, Math.max(4, (elapsed / typical) * 100)) : 30}%`, background: "var(--aurora)" }}
                />
              </div>
              {typical !== null && <p className="mt-1.5 text-center text-[10px] text-ink/70">{t("job.usually", { time: human(typical) })}</p>}
              {slow && <p className="mt-1 text-center text-[10px] text-ink/70">{t("job.slow")}</p>}
            </div>
          )}
        </div>
        {job.status === "queued" && job.queue_position ? (
          <p className="px-4 py-2.5 text-[11px] font-medium text-accent">
            {t("job.queuePosition", { position: job.queue_position, minutes: Math.max(1, Math.ceil((job.eta_seconds ?? 0) / 60)) })}
          </p>
        ) : null}
      </article>
    );
  }

  if (!first) {
    return <EmptyJobCard job={job} title={title} style={style} {...handlers} />;
  }

  return (
    <>
      <article className="tile rise spot group relative overflow-hidden rounded-[var(--radius-card)] bg-raised" style={style}>
        <button type="button" onClick={() => setOpen(true)} aria-label={`${t("job.open")}: ${title}`} className="block w-full text-left">
          {video ? (
            <video
              src={first.url}
              autoPlay
              muted
              loop
              playsInline
              preload="metadata"
              className="block h-auto w-full"
              style={{ aspectRatio: first.width && first.height ? first.width / first.height : undefined }}
            />
          ) : (
            <img src={first.preview_url || first.url} alt={job.prompt} loading="lazy" width={first.width} height={first.height} className="block h-auto w-full" />
          )}
        </button>
        <div className="pointer-events-none absolute left-2.5 top-2.5 flex gap-1.5">
          {video && (
            <span className="flex items-center gap-1 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold text-ink backdrop-blur">
              <Icon name="video" size={11} />
              {job.params.duration ? t("studio.seconds", { count: job.params.duration }) : ""}
            </span>
          )}
          {big >= 3840 && <span className="rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-bold text-accent backdrop-blur">{big >= 7680 ? "8K" : "4K"}</span>}
          {job.assets.length > 1 && <span className="rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-ink backdrop-blur">+{job.assets.length - 1}</span>}
        </div>
        {first.is_favorite && (
          <span className="pointer-events-none absolute right-2.5 top-2.5 text-accent-2">
            <Icon name="star" size={16} fill="currentColor" />
          </span>
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex translate-y-1 items-end justify-between gap-2 bg-gradient-to-t from-black/85 via-black/45 to-transparent p-3 pt-10 opacity-0 transition duration-300 group-focus-within:translate-y-0 group-focus-within:opacity-100 group-hover:translate-y-0 group-hover:opacity-100 [@media(hover:none)]:translate-y-0 [@media(hover:none)]:opacity-100 [&>*]:pointer-events-auto">
          <p className="line-clamp-2 min-w-0 flex-1 text-xs leading-snug text-ink">{title}</p>
          <div className="flex shrink-0 gap-1.5">
            <button type="button" className={quick} onClick={() => void toggleFavorite()} aria-label={first.is_favorite ? t("job.unfavorite") : t("job.favorite")} title={first.is_favorite ? t("job.unfavorite") : t("job.favorite")}>
              <Icon name="star" size={15} fill={first.is_favorite ? "currentColor" : "none"} className={first.is_favorite ? "text-accent-2" : ""} />
            </button>
            {handlers.onRemix && !isUpscaleJob && (
              <button type="button" className={quick} onClick={() => handlers.onRemix?.(job)} aria-label={t("job.remix")} title={t("job.remix")}>
                <Icon name="sparkle" size={15} />
              </button>
            )}
          </div>
        </div>
        {job.status === "done" && job.error && <p className="px-3 py-2 text-[11px] text-accent-3">{t("job.partial")}</p>}
      </article>
      {open && <JobDialog job={job} onClose={closeDialog} {...handlers} />}
    </>
  );
}
