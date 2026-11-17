// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import JobCard from "../components/JobCard";
import { Badge, Button, Card, ErrorText, inputClass, Label } from "../components/ui";
import type { Asset, Job, ModelInfo, Preset, Provider } from "../types";

const MAX_PROMPT = 1000;
const SIZES = ["small", "medium", "large"] as const;
type Mode = "image" | "video";

function watchJob(id: string, onUpdate: (job: Job) => void): () => void {
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

export function QuotaLine({ provider }: { provider: Provider }) {
  const { t } = useTranslation();
  const q = provider.quota;
  if (!q) return null;
  if (q.blocked_seconds > 0) {
    return (
      <p className="mt-1.5 text-[11px] text-danger">
        {t("studio.quotaBlocked", { minutes: Math.max(1, Math.ceil(q.blocked_seconds / 60)) })}
      </p>
    );
  }
  if (q.estimated_limit === null) {
    return <p className="mt-1.5 text-[11px] text-muted">{t("studio.quotaUnknown", { used: q.used_today })}</p>;
  }
  return (
    <p className="mt-1.5 text-[11px] text-muted">
      {t("studio.quotaLeft", { remaining: q.remaining, limit: q.estimated_limit })}{" "}
      <span className="opacity-70">
        ({q.source === "learned" ? t("studio.quota_learned", { count: q.observations }) : t("studio.quota_documented")})
      </span>
    </p>
  );
}

export default function Studio() {
  const { t } = useTranslation();
  const { reload } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [mode, setMode] = useState<Mode>("image");
  const [prompt, setPrompt] = useState("");
  const [modelKey, setModelKey] = useState("");
  const [aspect, setAspect] = useState("1:1");
  const [size, setSize] = useState<(typeof SIZES)[number]>("large");
  const [count, setCount] = useState(1);
  const [duration, setDuration] = useState<number | null>(null);
  const [startImage, setStartImage] = useState<Asset | null>(null);
  const [resolution, setResolution] = useState<"native" | "4k" | "8k">("native");
  const [presetId, setPresetId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const watchers = useRef(new Map<string, () => void>());

  const loadProviders = useCallback(async () => setProviders(await api<Provider[]>("/api/providers")), []);

  const upsertJob = useCallback(
    (job: Job) => {
      setJobs((prev) => {
        const rest = prev.filter((j) => j.id !== job.id);
        return [job, ...rest].sort((a, b) => b.created_at.localeCompare(a.created_at));
      });
      if (job.status === "done" || job.status === "failed") {
        watchers.current.get(job.id)?.();
        watchers.current.delete(job.id);
        void reload(); // credit balance (refunds)
        void loadProviders(); // learned quota estimates
      }
    },
    [reload, loadProviders],
  );

  const watch = useCallback(
    (id: string) => {
      if (!watchers.current.has(id)) watchers.current.set(id, watchJob(id, upsertJob));
    },
    [upsertJob],
  );

  useEffect(() => {
    void (async () => {
      const [pr, recent] = await Promise.all([
        api<Preset[]>("/api/presets"),
        api<Job[]>("/api/jobs?limit=12"),
        loadProviders(),
      ]);
      setPresets(pr);
      setJobs(recent);
      recent.filter((j) => j.status === "queued" || j.status === "running").forEach((j) => watch(j.id));
    })().catch(setError);
    const current = watchers.current;
    return () => current.forEach((stop) => stop());
  }, [watch, loadProviders]);

  // All (provider, model) pairs of the current mode.
  const choices = useMemo(
    () => providers.flatMap((p) => p.models.filter((m) => m.kind === mode).map((m) => ({ p, m }))),
    [providers, mode],
  );
  const selected = choices.find(({ p, m }) => `${p.id}|${m.id}` === modelKey);
  const provider = selected?.p;
  const model: ModelInfo | undefined = selected?.m;

  // Keep a valid model selected for the mode (prefer available, and image-capable when animating).
  useEffect(() => {
    if (selected || choices.length === 0) return;
    const pick =
      choices.find(({ p, m }) => p.available && (!startImage || m.accepts_image)) ??
      choices.find(({ p }) => p.available) ??
      choices[0];
    setModelKey(`${pick.p.id}|${pick.m.id}`);
  }, [choices, selected, startImage]);

  const ratios = useMemo(() => model?.aspect_ratios ?? ["1:1"], [model]);
  useEffect(() => {
    if (!ratios.includes(aspect)) setAspect(ratios[0]);
  }, [ratios, aspect]);
  useEffect(() => {
    if (model?.kind === "video" && (duration === null || !model.durations.includes(duration))) {
      setDuration(model.durations[0] ?? null);
    }
  }, [model, duration]);

  useEffect(() => {
    if (resolution !== "native" && !model?.upscale_targets.includes(resolution)) setResolution("native");
  }, [model, resolution]);

  const upscaleAsset = useCallback(
    async (asset: Asset, target: "4k" | "8k") => {
      setError(null);
      try {
        const job = await api<Job>(`/api/assets/${asset.id}/upscale`, { method: "POST", body: { target } });
        upsertJob(job);
        watch(job.id);
        void reload();
      } catch (err) {
        setError(err);
      }
    },
    [upsertJob, watch, reload],
  );

  const animate = useCallback((asset: Asset) => {
    setStartImage(asset);
    setMode("video");
    setModelKey(""); // re-pick a model that accepts a start image
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  // "Animate" pressed on the History page.
  useEffect(() => {
    const state = location.state as { animate?: Asset } | null;
    if (state?.animate) {
      animate(state.animate);
      navigate(".", { replace: true, state: null });
    }
  }, [location.state, animate, navigate]);

  const switchMode = (next: Mode) => {
    setMode(next);
    setModelKey("");
    if (next === "image") setStartImage(null);
  };

  const choosePreset = (id: string) => {
    setPresetId(id);
    const wanted = presets.find((p) => p.id === id)?.image_defaults.aspect_ratio;
    if (wanted && ratios.includes(wanted)) setAspect(wanted);
  };

  const submit = async () => {
    if (!provider || !model) return;
    setBusy(true);
    setError(null);
    try {
      const video = model.kind === "video";
      const job = await api<Job>("/api/jobs", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: {
          prompt,
          provider: provider.id,
          model: model.id,
          aspect_ratio: aspect,
          size,
          count: video ? 1 : count,
          preset_id: presetId || null,
          duration: video ? duration : null,
          image_asset_id: video && startImage && model.accepts_image ? startImage.id : null,
          upscale: resolution === "native" ? null : resolution,
        },
      });
      upsertJob(job);
      watch(job.id);
      void reload();
    } catch (err) {
      setError(err);
      void loadProviders();
    } finally {
      setBusy(false);
    }
  };

  const isVideo = mode === "video";
  const extra = resolution === "native" ? 0 : (model?.upscale_credits[resolution] ?? 0);
  const cost = ((model?.credit_cost ?? 1) + extra) * (isVideo ? 1 : count);
  const needsImage = Boolean(model?.requires_image && !startImage);
  const tab = (active: boolean) =>
    `flex-1 rounded-md px-3 py-1.5 text-sm font-medium ${active ? "bg-amber text-amber-ink" : "text-muted hover:text-ink"}`;

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Card className="h-fit lg:sticky lg:top-6">
        <div className="mb-4 flex gap-1 rounded-lg border border-line bg-bg p-1" role="tablist">
          <button role="tab" aria-selected={!isVideo} className={tab(!isVideo)} onClick={() => switchMode("image")}>
            {t("studio.mode_image")}
          </button>
          <button role="tab" aria-selected={isVideo} className={tab(isVideo)} onClick={() => switchMode("video")}>
            ▶ {t("studio.mode_video")}
          </button>
        </div>

        {isVideo && startImage && (
          <div className="mb-4 flex items-center gap-3 rounded-lg border border-line bg-bg p-2">
            <img src={startImage.preview_url || startImage.url} alt="" className="h-14 w-14 rounded-md object-cover" />
            <div className="flex-1 text-xs">
              <p className="font-semibold">{t("studio.startImage")}</p>
              {model && !model.accepts_image && <p className="text-danger">{t("errors.image_input_unsupported")}</p>}
            </div>
            <button onClick={() => setStartImage(null)} className="text-xs text-muted hover:text-ink">
              {t("studio.removeStartImage")}
            </button>
          </div>
        )}

        <Label htmlFor="prompt">{isVideo ? t("studio.videoPromptLabel") : t("studio.promptLabel")}</Label>
        <textarea
          id="prompt"
          rows={5}
          maxLength={MAX_PROMPT}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={isVideo ? t("studio.videoPromptPlaceholder") : t("studio.promptPlaceholder")}
          className={`${inputClass} resize-y`}
        />
        <p className="mt-1 text-right text-[11px] text-muted">
          {t("studio.chars", { count: prompt.length, max: MAX_PROMPT })}
        </p>

        <div className="mt-4">
          <Label htmlFor="model">{t("studio.model")}</Label>
          {choices.length === 0 ? (
            <p className="text-xs text-muted">
              {t("studio.noVideoModels")}{" "}
              <Link to="/settings" className="underline hover:text-ink">{t("nav.settings")}</Link>
            </p>
          ) : (
            <select id="model" value={modelKey} onChange={(e) => setModelKey(e.target.value)} className={inputClass}>
              {providers.map((p) => {
                const ms = p.models.filter((m) => m.kind === mode);
                if (ms.length === 0) return null;
                return (
                  <optgroup key={p.id} label={`${p.name} · ${p.tier === "free" ? t("studio.free") : t("studio.paid")}`}>
                    {ms.map((m) => (
                      <option key={m.id} value={`${p.id}|${m.id}`} disabled={!p.available}>
                        {m.label}
                        {!p.available ? ` (${t("studio.needsKey")})` : ""}
                      </option>
                    ))}
                  </optgroup>
                );
              })}
            </select>
          )}
          {provider && model && (
            <>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge tone={provider.tier === "free" ? "free" : "paid"}>
                  {provider.tier === "free" ? t("studio.free") : t("studio.paid")}
                </Badge>
                {provider.key_source === "user" && <Badge tone="muted">{t("studio.byok")}</Badge>}
                <Badge tone={model.commercial_use === "yes" ? "ok" : "muted"}>
                  {t(`studio.commercial_${model.commercial_use}`)}
                </Badge>
              </div>
              <QuotaLine provider={provider} />
            </>
          )}
          {choices.some(({ p }) => !p.available) && (
            <p className="mt-2 text-[11px] text-muted">
              <Link to="/settings" className="underline hover:text-ink">{t("studio.needsKey")}</Link>
            </p>
          )}
        </div>

        <div className="mt-4">
          <Label>{t("studio.preset")}</Label>
          <div className="flex flex-wrap gap-1.5">
            {[{ id: "" }, ...presets].map((p) => (
              <button
                key={p.id || "none"}
                type="button"
                onClick={() => choosePreset(p.id)}
                title={p.id ? t(`presets.${p.id}.desc`, { defaultValue: "" }) : undefined}
                className={`rounded-full border px-3 py-1 text-xs ${
                  presetId === p.id ? "border-amber bg-amber/15 text-amber" : "border-line text-muted hover:text-ink"
                }`}
              >
                {p.id ? t(`presets.${p.id}.name`, { defaultValue: p.id }) : t("studio.noPreset")}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-muted">{t("studio.presetHint")}</p>
        </div>

        <div className="mt-4">
          <Label>{t("studio.aspect")}</Label>
          <div className="flex flex-wrap gap-1.5">
            {["1:1", "16:9", "9:16", "4:3", "3:4"].map((r) => (
              <button
                key={r}
                type="button"
                disabled={!ratios.includes(r)}
                onClick={() => setAspect(r)}
                className={`rounded-md border px-2.5 py-1 text-xs disabled:opacity-30 ${
                  aspect === r ? "border-amber text-amber" : "border-line text-muted hover:text-ink"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="size">{t("studio.size")}</Label>
            <select id="size" value={size} onChange={(e) => setSize(e.target.value as typeof size)} className={inputClass}>
              {SIZES.map((s) => (
                <option key={s} value={s}>{t(`studio.size_${s}`)}</option>
              ))}
            </select>
          </div>
          {isVideo ? (
            <div>
              <Label htmlFor="duration">{t("studio.duration")}</Label>
              <select
                id="duration"
                value={duration ?? ""}
                onChange={(e) => setDuration(Number(e.target.value))}
                className={inputClass}
              >
                {[...(model?.durations ?? [])].sort((a, b) => a - b).map((d) => (
                  <option key={d} value={d}>{t("studio.seconds", { count: d })}</option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <Label htmlFor="count">{t("studio.count")}</Label>
              <select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))} className={inputClass}>
                {[1, 2, 3, 4].slice(0, model?.max_count ?? 4).map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        {model && model.upscale_targets.length > 0 && (
          <div className="mt-4">
            <Label>{t("studio.resolution")}</Label>
            <div className="flex gap-1.5">
              {(["native", ...model.upscale_targets] as const).map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setResolution(r)}
                  className={`flex-1 rounded-md border px-2.5 py-1.5 text-xs ${
                    resolution === r ? "border-amber bg-amber/15 text-amber" : "border-line text-muted hover:text-ink"
                  }`}
                >
                  {t(`studio.res_${r}`)}
                  {r !== "native" && (
                    <span className="block text-[10px] opacity-70">
                      {t("studio.resCost", { count: model.upscale_credits[r] ?? 0 })}
                    </span>
                  )}
                </button>
              ))}
            </div>
            {resolution !== "native" && (
              <p className="mt-1.5 text-[11px] text-muted">
                {isVideo ? t("studio.resHintVideo") : t("studio.resHintImage")}
              </p>
            )}
          </div>
        )}

        {isVideo && !startImage && <p className="mt-3 text-[11px] text-muted">{t("studio.startImageHint")}</p>}
        {needsImage && <p className="mt-2 text-[11px] text-danger">{t("studio.needsImage")}</p>}

        <Button
          className="mt-5 w-full"
          disabled={busy || prompt.trim().length < 3 || !provider?.available || needsImage}
          onClick={() => void submit()}
        >
          {busy ? t("studio.generating") : t("studio.generate")}
        </Button>
        <p className="mt-1.5 text-center text-[11px] text-muted">{t("studio.cost", { count: cost })}</p>
        <ErrorText error={error} />
      </Card>

      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">{t("studio.recent")}</h2>
        {jobs.length === 0 ? (
          <Card className="text-center text-sm text-muted">{t("studio.empty")}</Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {jobs.map((j) => (
              <JobCard
                key={j.id}
                job={j}
                onChange={upsertJob}
                onReuse={setPrompt}
                onAnimate={animate}
                onUpscale={(a, target) => void upscaleAsset(a, target)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
