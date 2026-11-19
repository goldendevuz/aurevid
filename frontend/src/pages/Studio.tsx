// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/icons";
import JobCard from "../components/JobCard";
import { retryJob, watchJob } from "../jobs";
import ModelPicker, { ModelSwatch } from "../components/ModelPicker";
import { Badge, Button, EmptyState, ErrorText, Segmented } from "../components/ui";
import { onFreeShare, priceOf } from "../pricing";
import type { Asset, Job, ModelInfo, Preset, Provider } from "../types";

const MAX_PROMPT = 1000;
const SIZES = ["small", "medium", "large"] as const;
const ALL_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"];
const RECIPE_ID = "image-animate-4k";
const MAX_COMPARE = 4;
type Mode = "image" | "video";
type Tool = "single" | "compare" | "recipe";

interface CompareEntry {
  key: string;
  label: string;
  cost: number;
  jobId?: string;
  error?: unknown;
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
  const [tool, setTool] = useState<Tool>("single");
  const [compareKeys, setCompareKeys] = useState<string[]>([]);
  const [compareRun, setCompareRun] = useState<CompareEntry[] | null>(null);
  const [videoKey, setVideoKey] = useState("");
  const [recipe4k, setRecipe4k] = useState(false);
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
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const closePicker = useCallback(() => setPicking(false), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const watchers = useRef(new Map<string, () => void>());
  const followRecipe = useRef<(id: string) => void>(() => undefined);

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
        const r = job.params.recipe;
        if (r?.next?.length && !r.next_job_id && !r.error) followRecipe.current(job.id);
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

  // A recipe step finished: the worker queues the next one (or records why it stopped). Follow it.
  useEffect(() => {
    followRecipe.current = (id: string) => {
      let tries = 0;
      const check = async () => {
        try {
          const parent = await api<Job>(`/api/jobs/${id}`);
          const r = parent.params.recipe;
          if (r?.next_job_id || r?.error) {
            setJobs((prev) => prev.map((j) => (j.id === parent.id ? parent : j)));
            if (r.next_job_id) {
              upsertJob(await api<Job>(`/api/jobs/${r.next_job_id}`));
              watch(r.next_job_id);
              void reload();
            }
            return;
          }
        } catch {
          /* transient */
        }
        if (++tries < 10) setTimeout(() => void check(), 1500);
      };
      setTimeout(() => void check(), 500);
    };
  }, [upsertJob, watch, reload]);

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

  // Compare and recipe tools work on image models; recipes animate with an image-capable video model.
  const imageChoices = useMemo(
    () => providers.flatMap((p) => p.models.filter((m) => m.kind === "image").map((m) => ({ p, m }))),
    [providers],
  );
  const animateChoices = useMemo(
    () => providers.flatMap((p) => p.models.filter((m) => m.kind === "video" && m.accepts_image && p.available).map((m) => ({ p, m }))),
    [providers],
  );
  const compared = useMemo(
    () => compareKeys.map((k) => imageChoices.find(({ p, m }) => `${p.id}|${m.id}` === k)).filter((c) => c !== undefined),
    [compareKeys, imageChoices],
  );
  const videoChoice = animateChoices.find(({ p, m }) => `${p.id}|${m.id}` === videoKey);
  useEffect(() => {
    if (tool === "recipe" && !videoChoice && animateChoices.length > 0) {
      setVideoKey(`${animateChoices[0].p.id}|${animateChoices[0].m.id}`);
    }
  }, [tool, videoChoice, animateChoices]);
  useEffect(() => {
    if (recipe4k && !videoChoice?.m.upscale_targets.includes("4k")) setRecipe4k(false);
  }, [recipe4k, videoChoice]);

  const ratios = useMemo(() => {
    const base = tool === "compare" && compared.length > 0 ? compared.map(({ m }) => m.aspect_ratios) : [model?.aspect_ratios ?? ["1:1"]];
    if (tool === "recipe" && videoChoice) base.push(videoChoice.m.aspect_ratios);
    const shared = ALL_RATIOS.filter((r) => base.every((list) => list.includes(r)));
    return shared.length > 0 ? shared : (model?.aspect_ratios ?? ["1:1"]);
  }, [tool, compared, model, videoChoice]);
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

  // Remix: restore every setting of a finished job (prompt, model, format, size, count, preset, duration, upscale).
  const remix = useCallback((job: Job) => {
    const video = job.kind === "video";
    setMode(video ? "video" : "image");
    setPrompt(job.prompt);
    setWantAspect(job.params.aspect_ratio);
    setAspect(job.params.aspect_ratio);
    if ((SIZES as readonly string[]).includes(job.params.size)) setSize(job.params.size as (typeof SIZES)[number]);
    setCount(video ? 1 : Math.max(1, job.count));
    setPresetId(job.preset_id ?? "");
    setDuration(video ? (job.params.duration ?? null) : null);
    setResolution(job.params.upscale ?? "native");
    setStartImage(null);
    setModelKey(`${job.provider}|${job.model}`); // falls back to a valid model if it is gone
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.getElementById("prompt")?.focus({ preventScroll: true });
  }, []);

  // "Animate" or "Remix" pressed on the History page.
  useEffect(() => {
    const state = location.state as { animate?: Asset; remix?: Job; prefill?: { prompt: string; aspect: string } } | null;
    if (!state) return;
    if (state.remix) remix(state.remix);
    if (state.animate) animate(state.animate);
    if (state.prefill) {
      setPrompt(state.prefill.prompt);
      setWantAspect(state.prefill.aspect);
      setAspect(state.prefill.aspect);
      if (!state.animate) setModelKey(""); // re-pick a model that supports this format
    }
    navigate(".", { replace: true, state: null });
  }, [location.state, animate, remix, navigate]);

  const uploadStart = async (file: File) => {
    setError(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const asset = await api<Asset>("/api/assets/upload", { method: "POST", form: fd });
      setStartImage(asset);
      // Keep the chosen model if it can take a start image; otherwise re-pick one that can.
      if (!model?.accepts_image) setModelKey("");
    } catch (err) {
      setError(err);
    } finally {
      setUploading(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setModelKey("");
    setTool("single");
    if (next === "image") setStartImage(null);
  };

  const toggleCompare = (key: string) =>
    setCompareKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : prev.length < MAX_COMPARE ? [...prev, key] : prev));

  const choosePreset = (id: string) => {
    setPresetId(id);
    const wanted = presets.find((p) => p.id === id)?.image_defaults.aspect_ratio;
    if (wanted && ratios.includes(wanted)) setAspect(wanted);
  };

  // One job per model through the normal endpoint; each model's refusal is shown in its own cell.
  const submitCompare = async () => {
    setBusy(true);
    setError(null);
    const run: CompareEntry[] = [];
    for (const { p, m } of compared) {
      const entry: CompareEntry = { key: `${p.id}|${m.id}`, label: m.label, cost: priceOf(m).total };
      try {
        const job = await api<Job>("/api/jobs", {
          method: "POST",
          headers: { "Idempotency-Key": crypto.randomUUID() },
          body: { prompt, provider: p.id, model: m.id, aspect_ratio: aspect, size, count: 1, preset_id: presetId || null },
        });
        entry.jobId = job.id;
        upsertJob(job);
        watch(job.id);
      } catch (err) {
        entry.error = err;
      }
      run.push(entry);
      setCompareRun([...run]);
    }
    void reload();
    void loadProviders();
    setBusy(false);
  };

  const submitRecipe = async () => {
    if (!provider || !model || !videoChoice) return;
    setBusy(true);
    setError(null);
    try {
      const job = await api<Job>(`/api/recipes/${RECIPE_ID}/run`, {
        method: "POST",
        body: {
          prompt,
          provider: provider.id,
          model: model.id,
          aspect_ratio: aspect,
          size,
          preset_id: presetId || null,
          video_provider: videoChoice.p.id,
          video_model: videoChoice.m.id,
          upscale: recipe4k ? "4k" : null,
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

  const submit = async () => {
    if (tool === "compare" && !isVideo) return submitCompare();
    if (tool === "recipe" && !isVideo) return submitRecipe();
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
  const activeTool: Tool = isVideo ? "single" : tool;
  const single = activeTool === "single";
  // Upfront price of exactly what will be sent (same formula as the backend).
  const price = priceOf(model, isVideo ? 1 : count, resolution);
  const total =
    activeTool === "compare"
      ? compared.reduce((sum, { m }) => sum + priceOf(m).total, 0)
      : activeTool === "recipe"
        ? priceOf(model).total + priceOf(videoChoice?.m, 1, recipe4k ? "4k" : null).total
        : price.total;
  const needsImage = Boolean(model?.requires_image && !startImage);
  const chip =
    "flex items-center gap-1.5 rounded-xl border border-line bg-bg/60 px-3 py-2 text-xs font-medium text-ink transition hover:border-white/20 focus-within:border-white/50";
  const selectChip = "cursor-pointer appearance-none bg-transparent pr-1 text-xs font-medium text-ink focus:outline-none [&>option]:bg-surface";
  const examples = (isVideo ? (["v1", "v2", "v3"] as const) : (["i1", "i2", "i3", "i4"] as const)).map((k) => t(`studio.example_${k}`));
  const canGenerate =
    !(busy || prompt.trim().length < 3) &&
    (activeTool === "compare"
      ? compared.length >= 2 && compared.every(({ p }) => p.available)
      : Boolean(provider?.available) && !needsImage && (activeTool !== "recipe" || Boolean(videoChoice)));

  return (
    <div>
      <section className="mx-auto max-w-4xl pb-8 pt-2 text-center sm:pt-8">
        <p className="rise mx-auto mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-medium text-muted backdrop-blur">
          <Icon name="sparkle" size={13} className="text-accent" />
          {t("studio.eyebrow")}
        </p>
        <h1 className="rise text-5xl font-bold leading-[1] tracking-[-0.04em] [--i:1] sm:text-7xl">
          <span className="block">{t("studio.heroLead")}</span>
          <span className="aurora-text block pb-1">{t("studio.heroAccent")}</span>
        </h1>
        <p className="rise mx-auto mt-5 max-w-xl text-sm text-muted [--i:2] sm:text-base">{t("studio.heroSub")}</p>
        <Link
          to="/marketing"
          className="rise mt-4 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-4 py-1.5 text-xs font-semibold text-accent transition hover:border-accent hover:bg-accent/20 [--i:2]"
        >
          <Icon name="megaphone" size={14} />
          {t("studio.makeAd")}
          <span aria-hidden>→</span>
        </Link>
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
        {!isVideo && (
          <div className="mb-3 flex justify-center">
            <Segmented
              label={t("tools.label")}
              value={tool}
              onChange={setTool}
              options={[
                { value: "single", label: t("tools.single") },
                { value: "compare", label: t("tools.compare") },
                { value: "recipe", label: t("tools.recipe") },
              ]}
            />
          </div>
        )}

        <div className="glass ring-aurora spot rise rounded-[28px] p-3 [--i:3] sm:p-4">
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

          {isVideo && !startImage && (
            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                const file = e.dataTransfer.files?.[0];
                if (file) void uploadStart(file);
              }}
              className={`mb-3 flex cursor-pointer items-center gap-3 rounded-2xl border border-dashed px-4 py-3 text-left transition focus-within:border-white/50 ${
                dragging || model?.requires_image ? "border-white/60 bg-white/10" : "border-line hover:border-white/25"
              }`}
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-raised text-accent">
                <Icon name="image" size={20} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium text-ink">
                  {uploading ? t("studio.uploading") : t("studio.uploadStart")}
                </span>
                <span className="block text-[11px] text-muted">{t("studio.uploadHint")}</span>
              </span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={uploading}
                className="sr-only"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  e.target.value = ""; // allow choosing the same file again
                  if (file) void uploadStart(file);
                }}
              />
            </label>
          )}

          {activeTool === "compare" && (
            <div className="mb-3 rounded-2xl border border-line bg-bg/60 p-3">
              <p className="mb-2 text-xs font-semibold">{t("compare.pick", { count: compared.length, max: MAX_COMPARE })}</p>
              <div className="flex flex-wrap gap-2">
                {imageChoices.map(({ p, m }) => {
                  const key = `${p.id}|${m.id}`;
                  const on = compareKeys.includes(key);
                  return (
                    <button
                      key={key}
                      type="button"
                      aria-pressed={on}
                      disabled={!p.available || (!on && compareKeys.length >= MAX_COMPARE)}
                      onClick={() => toggleCompare(key)}
                      className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
                        on ? "border-white/60 bg-white/10 text-ink" : "border-line text-muted hover:border-white/20 hover:text-ink"
                      }`}
                    >
                      <ModelSwatch seed={key} size={14} />
                      {m.label}
                      <span className="opacity-70">· {t("price.selection", { count: priceOf(m).total })}</span>
                      {onFreeShare(p) && <span className="text-ok">· {t("price.free")}</span>}
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-[11px] text-muted">{t("compare.hint")}</p>
            </div>
          )}

          {activeTool === "recipe" && (
            <div className="mb-3 rounded-2xl border border-line bg-bg/60 p-3 text-xs">
              <p className="font-semibold">{t("recipe.title")}</p>
              <p className="mt-0.5 text-[11px] text-muted">{t("recipe.desc")}</p>
              {animateChoices.length === 0 ? (
                <p className="mt-2 text-danger">{t("errors.recipe_step_unavailable")}</p>
              ) : (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <label className={chip}>
                    <Icon name="video" size={15} className="text-muted" />
                    <span className="sr-only">{t("recipe.videoModel")}</span>
                    <select value={videoKey} onChange={(e) => setVideoKey(e.target.value)} className={selectChip}>
                      {animateChoices.map(({ p, m }) => (
                        <option key={`${p.id}|${m.id}`} value={`${p.id}|${m.id}`}>
                          {m.label} ({t("price.selection", { count: m.credit_cost })})
                        </option>
                      ))}
                    </select>
                  </label>
                  {videoChoice?.m.upscale_targets.includes("4k") && (
                    <label className={`${chip} cursor-pointer`}>
                      <input type="checkbox" checked={recipe4k} onChange={(e) => setRecipe4k(e.target.checked)} />
                      {t("recipe.upscale4k")} ({t("studio.resCost", { count: videoChoice.m.upscale_credits["4k"] ?? 0 })})
                    </label>
                  )}
                </div>
              )}
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
            {activeTool === "compare" ? null : choices.length === 0 ? (
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
                {model?.has_audio && <Icon name="sound" size={14} className="shrink-0 text-accent" title={t("studio.withAudio")} />}
                <Icon name="chevron" size={14} className="text-muted" />
              </button>
            )}

            <label className={chip}>
              <Icon name="ratio" size={15} className="text-muted" />
              <span className="sr-only">{t("studio.aspect")}</span>
              <select value={aspect} onChange={(e) => setAspect(e.target.value)} className={selectChip}>
                {ALL_RATIOS.map((r) => (
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
              single && <label className={chip}>
                <Icon name="layers" size={15} className="text-muted" />
                <span className="sr-only">{t("studio.count")}</span>
                <select value={count} onChange={(e) => setCount(Number(e.target.value))} className={selectChip}>
                  {[1, 2, 3, 4].slice(0, model?.max_count ?? 4).map((n) => (
                    <option key={n} value={n}>{n}×</option>
                  ))}
                </select>
              </label>
            )}

            {single && model && model.upscale_targets.length > 0 && (
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
             {busy ? t("studio.generating") : activeTool === "compare" ? t("compare.send", { count: compared.length }) : t("studio.generate")}
           </Button>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-2 pt-3 text-[11px] text-muted">
            <p>
              <span className="font-medium text-ink/90">
                {price.count > 1 && single ? t("price.selectionMany", { count: total, n: price.count, each: price.each }) : t("studio.cost", { count: total })}
              </span>
              {single && onFreeShare(provider) && <span className="text-ok"> · {t("price.freeShare")}</span>} · <span className="tabular-nums">{t("studio.chars", { count: prompt.length, max: MAX_PROMPT })}</span>
            </p>
            {single && provider && model && (
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <Badge tone={provider.tier === "free" ? "free" : "paid"}>
                  {provider.tier === "free" ? t("studio.free") : t("studio.paid")}
                </Badge>
                {provider.key_source === "user" && <Badge tone="muted">{t("studio.byok")}</Badge>}
                {provider.key_source === "server" && provider.free_left !== null && <Badge tone="free">{t("studio.freeLeft", { count: provider.free_left })}</Badge>}
                <Badge tone={model.commercial_use === "yes" ? "ok" : "muted"}>{t(`studio.commercial_${model.commercial_use}`)}</Badge>
                <QuotaLine provider={provider} />
              </div>
            )}
          </div>
          {isVideo && <p className="px-2 pt-2 text-[11px] text-muted">{t("studio.videoWait")}</p>}
          {isVideo && model?.has_audio && (
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2 pt-2 text-[11px] text-muted">
              <Icon name="sound" size={13} className="shrink-0 text-accent" />
              <span>{t("studio.audioHint")}</span>
              <button
                type="button"
                onClick={() => setPrompt((p) => (p.trim() ? `${p.trim()} ${t("studio.audioExample")}` : t("studio.audioExample")))}
                className="font-medium text-accent hover:underline"
              >
                {t("studio.audioInsert")}
              </button>
            </p>
          )}
          {isVideo && !startImage && <p className="px-2 pt-2 text-[11px] text-muted">{t("studio.startImageHint")}</p>}
          {needsImage && <p className="px-2 pt-2 text-[11px] text-danger">{t("studio.needsImage")}</p>}
          {single && resolution !== "native" && (
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

        {compareRun && compareRun.length > 0 && (
          <div className="mt-6" aria-live="polite">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-lg tracking-[0.02em]">{t("compare.results")}</h2>
              <button type="button" onClick={() => setCompareRun(null)} className="text-xs text-muted hover:text-ink">{t("studio.close")}</button>
            </div>
            <div className={`grid gap-3 ${compareRun.length > 2 ? "grid-cols-2 lg:grid-cols-4" : "grid-cols-2"}`}>
              {compareRun.map((c) => {
                const job = jobs.find((j) => j.id === c.jobId);
                const asset = job?.assets[0];
                return (
                  <figure key={c.key} className="overflow-hidden rounded-2xl border border-line bg-raised/40">
                    <div className="grid aspect-square place-items-center bg-bg/60">
                      {asset ? (
                        <img src={asset.preview_url || asset.url} alt={job?.prompt ?? ""} className="h-full w-full object-cover" />
                      ) : (
                        <span className="px-2 text-center text-[11px] text-muted">
                          {c.error ? "" : job ? t(`job.${job.status}`) : t("job.queued")}
                        </span>
                      )}
                    </div>
                    <figcaption className="p-2 text-[11px]">
                      <p className="truncate font-semibold text-ink">{c.label}</p>
                      <p className="text-muted">{t("price.selection", { count: c.cost })}</p>
                      {job?.status === "failed" && <p className="text-danger">{job.error}</p>}
                      {c.error ? <ErrorText error={c.error} /> : null}
                    </figcaption>
                  </figure>
                );
              })}
            </div>
          </div>
        )}

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
                    presetId === p.id ? "border-white/60 bg-white/10 text-ink" : "border-line text-muted hover:border-white/20 hover:text-ink"
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
                  className="max-w-full truncate rounded-xl border border-line bg-raised/30 px-3 py-2 text-left text-xs text-muted transition hover:border-white/30 hover:text-ink"
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
          <h2 id="recent-title" className="text-3xl tracking-[0.02em]">{t("studio.recent")}</h2>
          <Link to="/history" className="inline-flex items-center gap-1 text-xs font-medium text-muted transition hover:text-ink">
            {t("nav.history")}
            <Icon name="arrow" size={13} />
          </Link>
        </div>
        {jobs.length === 0 ? (
          <EmptyState icon={<Icon name="sparkle" size={22} />} title={t("studio.empty")} hint={t("studio.emptyHint")} />
        ) : (
          <div className="masonry columns-1 sm:columns-2 xl:columns-3">
            {jobs.map((j, i) => (
              <JobCard
                key={j.id}
                job={j}
                index={i}
                onChange={upsertJob}
                onRemix={remix}
                onRetry={async (job) => {
                  const created = await retryJob(job);
                  upsertJob(created);
                  watch(created.id);
                  void reload();
                }}
                onDelete={async (job) => {
                  await api(`/api/jobs/${job.id}`, { method: "DELETE" });
                  setJobs((prev) => prev.filter((x) => x.id !== job.id));
                }}
                onAnimate={animate}
                onUpscale={(a, target) => void upscaleAsset(a, target)}
              />
            ))}
          </div>
        )}
      </section>

      {picking && (
        <ModelPicker
          choices={choices}
          value={modelKey}
          mode={mode}
          onSelect={setModelKey}
          onClose={closePicker}
          count={isVideo ? 1 : count}
          upscale={resolution === "native" ? null : resolution}
        />
      )}
    </div>
  );
}
