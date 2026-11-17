// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/icons";
import JobCard from "../components/JobCard";
import ModelPicker, { ModelSwatch } from "../components/ModelPicker";
import { Badge, Button, EmptyState, ErrorText, Segmented } from "../components/ui";
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
      <p className="text-[11px] text-danger">
        {t("studio.quotaBlocked", { minutes: Math.max(1, Math.ceil(q.blocked_seconds / 60)) })}
      </p>
    );
  }
  if (q.estimated_limit === null) {
    return <p className="text-[11px] text-muted">{t("studio.quotaUnknown", { used: q.used_today })}</p>;
  }
  return (
    <p className="text-[11px] text-muted">
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
  const [wantAspect, setWantAspect] = useState<string | null>(null);
  const [presetId, setPresetId] = useState<string>("");
  const [picking, setPicking] = useState(false);
  const closePicker = useCallback(() => setPicking(false), []);
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
      (wantAspect
        ? choices.find(({ p, m }) => p.available && m.aspect_ratios.includes(wantAspect) && (!startImage || m.accepts_image))
        : undefined) ??
      choices.find(({ p, m }) => p.available && (!startImage || m.accepts_image)) ??
      choices.find(({ p }) => p.available) ??
      choices[0];
    setModelKey(`${pick.p.id}|${pick.m.id}`);
  }, [choices, selected, startImage, wantAspect]);

  const ratios = useMemo(() => model?.aspect_ratios ?? ["1:1"], [model]);
  useEffect(() => {
    if (!selected) return; // wait until a model is chosen (keeps a prefilled format)
    if (!ratios.includes(aspect)) setAspect(ratios[0]);
  }, [ratios, aspect, selected]);
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
    const state = location.state as { animate?: Asset; prefill?: { prompt: string; aspect: string } } | null;
    if (!state) return;
    if (state.animate) animate(state.animate);
    if (state.prefill) {
      setPrompt(state.prefill.prompt);
      setWantAspect(state.prefill.aspect);
      setAspect(state.prefill.aspect);
      if (!state.animate) setModelKey(""); // re-pick a model that supports this format
    }
    navigate(".", { replace: true, state: null });
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
  const chip =
    "flex items-center gap-1.5 rounded-xl border border-line bg-bg/60 px-3 py-2 text-xs font-medium text-ink transition hover:border-white/20 focus-within:border-accent-2";
  const selectChip = "cursor-pointer appearance-none bg-transparent pr-1 text-xs font-medium text-ink focus:outline-none [&>option]:bg-surface";
  const examples = (isVideo ? (["v1", "v2", "v3"] as const) : (["i1", "i2", "i3", "i4"] as const)).map((k) => t(`studio.example_${k}`));
  const canGenerate = !(busy || prompt.trim().length < 3 || !provider?.available || needsImage);

  return (
    <div>
      <section className="mx-auto max-w-4xl pb-8 pt-2 text-center sm:pt-6">
        <p className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-medium text-muted">
          <Icon name="sparkle" size={13} className="text-accent" />
          {t("studio.eyebrow")}
        </p>
        <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
          <span className="block">{t("studio.heroLead")}</span>
          <span className="aurora-text block pb-1">{t("studio.heroAccent")}</span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-sm text-muted sm:text-base">{t("studio.heroSub")}</p>
      </section>

      <section className="mx-auto max-w-4xl" aria-label={t("studio.composer")}>
        <div className="mb-3 flex justify-center">
          <Segmented
            label={t("studio.mode")}
            value={mode}
            onChange={switchMode}
            options={[
              { value: "image", label: <span className="flex items-center gap-1.5"><Icon name="image" size={15} />{t("studio.mode_image")}</span> },
              { value: "video", label: <span className="flex items-center gap-1.5"><Icon name="video" size={15} />{t("studio.mode_video")}</span> },
            ]}
          />
        </div>

        <div className="glass ring-aurora rounded-[24px] p-3 sm:p-4">
          {isVideo && startImage && (
            <div className="mb-3 flex items-center gap-3 rounded-2xl border border-line bg-bg/60 p-2">
              <img src={startImage.preview_url || startImage.url} alt="" className="h-14 w-14 rounded-xl object-cover" />
              <div className="flex-1 text-xs">
                <p className="font-semibold">{t("studio.startImage")}</p>
                {model && !model.accepts_image && <p className="text-danger">{t("errors.image_input_unsupported")}</p>}
              </div>
              <button onClick={() => setStartImage(null)} className="rounded-lg px-2 py-1 text-xs text-muted hover:bg-white/[0.06] hover:text-ink">
                {t("studio.removeStartImage")}
              </button>
            </div>
          )}

          <label htmlFor="prompt" className="sr-only">{isVideo ? t("studio.videoPromptLabel") : t("studio.promptLabel")}</label>
          <textarea
            id="prompt"
            rows={3}
            maxLength={MAX_PROMPT}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={isVideo ? t("studio.videoPromptPlaceholder") : t("studio.promptPlaceholder")}
            className="block w-full resize-y rounded-2xl bg-transparent px-3 py-2 text-base leading-relaxed text-ink placeholder:text-muted/60 focus:outline-none sm:text-lg"
          />

          <div className="flex flex-wrap items-end justify-between gap-3 px-1 pt-2">
           <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            {choices.length === 0 ? (
              <p className="text-xs text-muted">
                {t("studio.noVideoModels")}{" "}
                <Link to="/settings" className="underline hover:text-ink">{t("nav.settings")}</Link>
              </p>
            ) : (
              <button
                type="button"
                onClick={() => setPicking(true)}
                aria-haspopup="dialog"
                aria-label={`${t("studio.model")}: ${model?.label ?? ""}`}
                className={`${chip} max-w-full`}
              >
                <ModelSwatch seed={modelKey || "none"} size={20} />
                <span className="truncate">{model?.label ?? t("studio.model")}</span>
                <Icon name="chevron" size={14} className="text-muted" />
              </button>
            )}

            <label className={chip}>
              <Icon name="ratio" size={15} className="text-muted" />
              <span className="sr-only">{t("studio.aspect")}</span>
              <select value={aspect} onChange={(e) => setAspect(e.target.value)} className={selectChip}>
                {["1:1", "16:9", "9:16", "4:3", "3:4"].map((r) => (
                  <option key={r} value={r} disabled={!ratios.includes(r)}>{r}</option>
                ))}
              </select>
            </label>

            <label className={chip}>
              <Icon name="expand" size={15} className="text-muted" />
              <span className="sr-only">{t("studio.size")}</span>
              <select value={size} onChange={(e) => setSize(e.target.value as typeof size)} className={selectChip}>
                {SIZES.map((x) => (
                  <option key={x} value={x}>{t(`studio.size_${x}`)}</option>
                ))}
              </select>
            </label>

            {isVideo ? (
              <label className={chip}>
                <Icon name="clock" size={15} className="text-muted" />
                <span className="sr-only">{t("studio.duration")}</span>
                <select value={duration ?? ""} onChange={(e) => setDuration(Number(e.target.value))} className={selectChip}>
                  {[...(model?.durations ?? [])].sort((a, b) => a - b).map((d) => (
                    <option key={d} value={d}>{t("studio.seconds", { count: d })}</option>
                  ))}
                </select>
              </label>
            ) : (
              <label className={chip}>
                <Icon name="layers" size={15} className="text-muted" />
                <span className="sr-only">{t("studio.count")}</span>
                <select value={count} onChange={(e) => setCount(Number(e.target.value))} className={selectChip}>
                  {[1, 2, 3, 4].slice(0, model?.max_count ?? 4).map((n) => (
                    <option key={n} value={n}>{n}×</option>
                  ))}
                </select>
              </label>
            )}

            {model && model.upscale_targets.length > 0 && (
              <label className={chip}>
                <Icon name="wand" size={15} className="text-muted" />
                <span className="sr-only">{t("studio.resolution")}</span>
                <select value={resolution} onChange={(e) => setResolution(e.target.value as typeof resolution)} className={selectChip}>
                  {(["native", ...model.upscale_targets] as const).map((r) => (
                    <option key={r} value={r}>
                      {t(`studio.res_${r}`)}
                      {r !== "native" ? ` (${t("studio.resCost", { count: model.upscale_credits[r] ?? 0 })})` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}

           </div>
           <Button className="w-full min-w-32 py-2.5 sm:w-auto" disabled={!canGenerate} onClick={() => void submit()}>
             <Icon name="sparkle" size={17} />
             {busy ? t("studio.generating") : t("studio.generate")}
           </Button>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-2 pt-3 text-[11px] text-muted">
            <p>
              {t("studio.cost", { count: cost })} · <span className="tabular-nums">{t("studio.chars", { count: prompt.length, max: MAX_PROMPT })}</span>
            </p>
            {provider && model && (
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <Badge tone={provider.tier === "free" ? "free" : "paid"}>
                  {provider.tier === "free" ? t("studio.free") : t("studio.paid")}
                </Badge>
                {provider.key_source === "user" && <Badge tone="muted">{t("studio.byok")}</Badge>}
                <Badge tone={model.commercial_use === "yes" ? "ok" : "muted"}>{t(`studio.commercial_${model.commercial_use}`)}</Badge>
                <QuotaLine provider={provider} />
              </div>
            )}
          </div>
          {isVideo && <p className="px-2 pt-2 text-[11px] text-muted">{t("studio.videoWait")}</p>}
          {isVideo && !startImage && <p className="px-2 pt-2 text-[11px] text-muted">{t("studio.startImageHint")}</p>}
          {needsImage && <p className="px-2 pt-2 text-[11px] text-danger">{t("studio.needsImage")}</p>}
          {resolution !== "native" && (
            <p className="px-2 pt-2 text-[11px] text-muted">{isVideo ? t("studio.resHintVideo") : t("studio.resHintImage")}</p>
          )}
          {choices.some(({ p }) => !p.available) && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 px-2 pt-2 text-[11px] text-muted">
              <Link to="/settings" className="underline hover:text-ink">{t("studio.needsKey")}</Link>
              {[...new Map(choices.filter(({ p }) => !p.available && p.key_url).map(({ p }) => [p.id, p])).values()].map((p) => (
                <a key={p.id} href={p.key_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">
                  <Icon name="key" size={12} />
                  {p.name}: {t("settings.getKey")} ↗
                </a>
              ))}
            </div>
          )}
          <ErrorText error={error} />
        </div>

        {presets.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 flex items-center justify-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
              <Icon name="camera" size={13} />
              {t("studio.preset")}
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {[{ id: "" }, ...presets].map((p) => (
                <button
                  key={p.id || "none"}
                  type="button"
                  aria-pressed={presetId === p.id}
                  onClick={() => choosePreset(p.id)}
                  title={p.id ? t(`presets.${p.id}.desc`, { defaultValue: "" }) : undefined}
                  className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition ${
                    presetId === p.id ? "border-accent-2/70 bg-accent-2/15 text-ink" : "border-line text-muted hover:border-white/20 hover:text-ink"
                  }`}
                >
                  {p.id ? t(`presets.${p.id}.name`, { defaultValue: p.id }) : t("studio.noPreset")}
                </button>
              ))}
            </div>
            <p className="mt-2 text-center text-[11px] text-muted">{t("studio.presetHint")}</p>
          </div>
        )}

        {prompt.trim() === "" && (
          <div className="mt-6">
            <p className="mb-2 text-center text-[11px] font-medium uppercase tracking-[0.08em] text-muted">{t("studio.tryThese")}</p>
            <div className="flex flex-wrap justify-center gap-2">
              {examples.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setPrompt(ex)}
                  className="max-w-full truncate rounded-xl border border-line bg-raised/30 px-3 py-2 text-left text-xs text-muted transition hover:border-accent-2/50 hover:text-ink"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
      </section>

      <section className="mt-14" aria-labelledby="recent-title">
        <div className="mb-4 flex items-center justify-between">
          <h2 id="recent-title" className="text-lg font-semibold tracking-tight">{t("studio.recent")}</h2>
          <Link to="/history" className="inline-flex items-center gap-1 text-xs font-medium text-muted transition hover:text-ink">
            {t("nav.history")}
            <Icon name="arrow" size={13} />
          </Link>
        </div>
        {jobs.length === 0 ? (
          <EmptyState icon={<Icon name="sparkle" size={22} />} title={t("studio.empty")} hint={t("studio.emptyHint")} />
        ) : (
          <div className="grid items-start gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
      </section>

      {picking && (
        <ModelPicker choices={choices} value={modelKey} mode={mode} onSelect={setModelKey} onClose={closePicker} />
      )}
    </div>
  );
}
