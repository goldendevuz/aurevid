// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import type { Asset, Job } from "../types";
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
      className="mt-2 space-y-2 rounded-lg border border-line bg-bg p-3"
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

  return (
    <article className="rounded-[var(--radius-card)] border border-line bg-surface p-3">
      <div className="mb-2 flex items-start justify-between gap-3">
        <p className="line-clamp-2 text-sm text-ink">
          {job.provider === "local" && job.params.upscale
            ? `⤢ ${t("job.upscaleTo", { target: job.params.upscale.toUpperCase() })}`
            : job.prompt}
        </p>
        <Badge tone={tone}>{t(`job.${job.status}`)}</Badge>
      </div>
      <p className="mb-2 text-[11px] text-muted">
        {job.kind === "video" ? "▶ " : ""}
        {job.provider} · {job.params.aspect_ratio} ·{" "}
        {job.kind === "video" ? t("studio.seconds", { count: job.params.duration ?? 0 }) : `${job.count}×`}
        {job.preset_id ? ` · ${t(`presets.${job.preset_id}.name`, { defaultValue: job.preset_id })}` : ""}
      </p>
      {job.status === "queued" && job.queue_position ? (
        <p className="mb-2 text-[11px] text-amber">
          {t("job.queuePosition", {
            position: job.queue_position,
            minutes: Math.max(1, Math.ceil((job.eta_seconds ?? 0) / 60)),
          })}
        </p>
      ) : null}
      {(job.status === "queued" || job.status === "running") && (
        <div className="grid grid-cols-2 gap-2">
          {Array.from({ length: job.count }).map((_, i) => (
            <div key={i} className="aspect-square animate-pulse rounded-lg bg-raised" />
          ))}
        </div>
      )}
      {job.status === "failed" && (
        <p className="text-xs text-danger">
          {job.error} {t("job.refunded")}
        </p>
      )}
      {job.status === "done" && job.error && <p className="mb-2 text-xs text-amber">{t("job.partial")}</p>}
      {job.assets.length > 0 && (
        <div className={`grid gap-2 ${job.kind === "video" ? "grid-cols-1" : "grid-cols-2"}`}>
          {job.assets.map((a) => (
            <figure key={a.id} className="group relative">
              {a.mime.startsWith("video/") ? (
                <video
                  src={a.url}
                  controls
                  loop
                  muted
                  playsInline
                  preload="metadata"
                  aria-label={job.prompt}
                  className="h-auto w-full rounded-lg bg-raised"
                />
              ) : (
                <a href={a.url} target="_blank" rel="noopener" title={t("job.open")}>
                  <img
                    src={a.preview_url || a.url}
                    alt={job.prompt}
                    loading="lazy"
                    width={a.width}
                    height={a.height}
                    className="h-auto w-full rounded-lg bg-raised"
                  />
                </a>
              )}
              <figcaption className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted">
                <span className="rounded bg-raised px-1.5 text-ink/80">
                  {a.width}×{a.height}
                  {Math.max(a.width, a.height) >= 7680 ? " · 8K" : Math.max(a.width, a.height) >= 3840 ? " · 4K" : ""}
                </span>
                {a.mime.startsWith("video/") && (
                  <a href={a.url} download className="hover:text-ink">
                    ⬇ {t("job.download")}
                  </a>
                )}
                {onUpscale &&
                  a.mime.startsWith("image/") &&
                  (["4k", "8k"] as const)
                    .filter((target) => Math.max(a.width, a.height) < (target === "4k" ? 3840 : 7680))
                    .map((target) => (
                      <button key={target} onClick={() => onUpscale(a, target)} className="hover:text-amber">
                        ⤢ {t("job.upscaleTo", { target: target.toUpperCase() })}
                      </button>
                    ))}
                {onAnimate && a.mime.startsWith("image/") && (
                  <button onClick={() => onAnimate(a)} className="font-semibold text-amber hover:brightness-110">
                    ▶ {t("job.animate")}
                  </button>
                )}
                <button onClick={() => void toggleFavorite(a)} className="hover:text-amber">
                  {a.is_favorite ? `★ ${t("job.unfavorite")}` : `☆ ${t("job.favorite")}`}
                </button>
                <button onClick={() => setReporting(reporting === a.id ? null : a.id)} className="hover:text-ink">
                  {t("job.report")}
                </button>
                <button onClick={() => void remove(a)} className="hover:text-danger">
                  {t("job.delete")}
                </button>
              </figcaption>
              {reporting === a.id && <ReportForm asset={a} onClose={() => setReporting(null)} />}
            </figure>
          ))}
        </div>
      )}
      {onReuse && (
        <button onClick={() => onReuse(job.prompt)} className="mt-2 text-[11px] text-muted hover:text-amber">
          ↺ {t("job.copyPrompt")}
        </button>
      )}
    </article>
  );
}
