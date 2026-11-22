// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Icon } from "../components/icons";
import JobCard from "../components/JobCard";
import { retryJob, watchJob } from "../jobs";
import ModelPicker, { ModelSwatch } from "../components/ModelPicker";
import VoiceButton from "../components/VoiceButton";
import { BuyCredits } from "../components/BuyCredits";
import { Badge, Button, ErrorText, Segmented } from "../components/ui";
import StoryCard from "../components/StoryCard";
import { defaultResolution, onFreeShare, priceOf } from "../pricing";
import {
  VIDEO_TIERS,
  activeTier,
  estimatedUsd,
  expectedDimensions,
  isDraft,
  usdLabel,
  type TierId,
} from "../quality";
import {
  MAX_SCENES,
  MIN_SCENES,
  STORY_SCENE_SECONDS,
  addScene,
  canSubmitStory,
  removeScene,
  storyCapable,
  storyPrice,
  trimScenes,
} from "../stories";
import { useStories } from "../useStories";
import type { Asset, Job, ModelInfo, Preset, Provider, Story } from "../types";

const MAX_PROMPT = 1000;
const SIZES = ["small", "medium", "large"] as const;
const ALL_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"];
const RECIPE_ID = "image-animate-4k";
const MAX_COMPARE = 4;
type Mode = "image" | "video";
type Tool = "single" | "compare" | "recipe";
type SceneMode = "single" | "multi";

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
  const { reload, user } = useAuth();
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
  const [endImage, setEndImage] = useState<Asset | null>(null);
  const [resolution, setResolution] = useState<"native" | "2k" | "4k" | "8k">("native");
  const [videoRes, setVideoRes] = useState<string | null>(null);
  const [publish, setPublish] = useState(false);
  const [publishTarget, setPublishTarget] = useState<"2k" | "4k">("2k");
  const [wantAspect, setWantAspect] = useState<string | null>(null);
  const [presetId, setPresetId] = useState<string>("");

  const [picking, setPicking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showBuyCredits, setShowBuyCredits] = useState(false);

  // Popovers in left panel
  const [activePopover, setActivePopover] = useState<"aspect" | "duration" | "resolution" | null>(null);

  // Right canvas tab & filter controls
  const [canvasTab, setCanvasTab] = useState<"history" | "how-it-works">("history");
  const [historyFilter, setHistoryFilter] = useState<"all" | "image" | "video" | "favorites">("all");
  const [gridCols, setGridCols] = useState<2 | 3 | 4>(2);
  const [isListView, setIsListView] = useState(false);

  const closePicker = useCallback(() => setPicking(false), []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [sceneMode, setSceneMode] = useState<SceneMode>("single");
  const [scenePrompts, setScenePrompts] = useState<string[]>(["", ""]);

  // Expand prompt state (P1)
  const [expandBusy, setExpandBusy] = useState(false);
  const [expandError, setExpandError] = useState<string | null>(null);
  const [preExpandPrompt, setPreExpandPrompt] = useState<string | null>(null);

  const watchers = useRef(new Map<string, () => void>());
  const followRecipe = useRef<(id: string) => void>(() => undefined);

  const loadProviders = useCallback(async () => setProviders(await api<Provider[]>("/api/providers")), []);

  const refreshAccount = useCallback(() => {
    void reload();
    void loadProviders();
  }, [reload, loadProviders]);

  const { stories, load: loadStories, track: trackStory, retryScene, restitch, remove: removeStory } = useStories(12, refreshAccount);

  const upsertJob = useCallback(
    (job: Job) => {
      setJobs((prev) => {
        const rest = prev.filter((j) => j.id !== job.id);
        return [job, ...rest].sort((a, b) => b.created_at.localeCompare(a.created_at));
      });
      if (job.status === "done" || job.status === "failed") {
        watchers.current.get(job.id)?.();
        watchers.current.delete(job.id);
        void reload();
        void loadProviders();
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
      await loadStories();
      recent.filter((j) => j.status === "queued" || j.status === "running").forEach((j) => watch(j.id));
    })().catch(setError);
    const current = watchers.current;
    return () => current.forEach((stop) => stop());
  }, [watch, loadProviders, loadStories]);

  useEffect(() => {
    const onKeysUpdated = () => {
      void loadProviders();
    };
    window.addEventListener("aurevid:keys-updated", onKeysUpdated);
    window.addEventListener("focus", onKeysUpdated);
    return () => {
      window.removeEventListener("aurevid:keys-updated", onKeysUpdated);
      window.removeEventListener("focus", onKeysUpdated);
    };
  }, [loadProviders]);

  const hasStoryModels = useMemo(() => providers.some((p) => p.models.some(storyCapable)), [providers]);
  const multiWanted = mode === "video" && sceneMode === "multi" && hasStoryModels;

  const choices = useMemo(
    () =>
      providers
        .flatMap((p) => p.models.filter((m) => m.kind === mode && (!multiWanted || storyCapable(m))).map((m) => ({ p, m })))
        .sort((a, b) => Number(a.p.id === "modal_video") - Number(b.p.id === "modal_video")),
    [providers, mode, multiWanted],
  );

  const inactiveModels = useMemo(
    () => providers.flatMap((p) => p.inactive_models ?? []).filter((m) => m.kind === mode),
    [providers, mode],
  );

  const selected = choices.find(({ p, m }) => `${p.id}|${m.id}` === modelKey);
  const provider = selected?.p;
  const model: ModelInfo | undefined = selected?.m;

  useEffect(() => {
    if (selected || choices.length === 0) return;
    const standard = mode === "video" ? choices.find(({ p, m }) => p.available && activeTier(p.id, m.id, defaultResolution(m)) === "standard") : undefined;
    const pick =
      standard ??
      (wantAspect
        ? choices.find(({ p, m }) => p.available && m.aspect_ratios.includes(wantAspect) && (!startImage || m.accepts_image))
        : undefined) ??
      choices.find(({ p, m }) => p.available && (!startImage || m.accepts_image)) ??
      choices.find(({ p }) => p.available) ??
      choices[0];
    setModelKey(`${pick.p.id}|${pick.m.id}`);
  }, [choices, selected, startImage, wantAspect, mode]);

  useEffect(() => {
    if (model?.resolutions?.length && (!videoRes || !model.resolutions.includes(videoRes))) setVideoRes(defaultResolution(model));
    if (!model?.resolutions?.length && videoRes) setVideoRes(null);
  }, [model, videoRes]);

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

  useEffect(() => {
    if (publish && model && !model.publish_quality) setPublish(false);
  }, [publish, model]);

  const publishChoice = imageChoices.find(({ m }) => m.publish_quality);
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
    if (!selected) return;
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
    async (asset: Asset, target: "2k" | "4k" | "8k") => {
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

  const editAsset = useCallback(
    async (asset: Asset, instruction: string) => {
      const job = await api<Job>(`/api/assets/${asset.id}/edit`, { method: "POST", body: { instruction } });
      upsertJob(job);
      watch(job.id);
      void reload();
    },
    [upsertJob, watch, reload],
  );

  const animate = useCallback((asset: Asset) => {
    setStartImage(asset);
    setMode("video");
    setModelKey("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

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
    const publishJob = job.params.quality === "publish";
    setPublish(publishJob);
    if (publishJob && (job.params.upscale === "2k" || job.params.upscale === "4k")) setPublishTarget(job.params.upscale);
    setResolution(publishJob ? "native" : (job.params.upscale ?? "native"));
    setVideoRes(job.params.resolution ?? null);
    setStartImage(null);
    setModelKey(`${job.provider}|${job.model}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.getElementById("prompt")?.focus({ preventScroll: true });
  }, []);

  useEffect(() => {
    const state = location.state as { animate?: Asset; remix?: Job; prefill?: { prompt: string; aspect: string } } | null;
    if (!state) return;
    if (state.remix) remix(state.remix);
    if (state.animate) animate(state.animate);
    if (state.prefill) {
      setPrompt(state.prefill.prompt);
      setWantAspect(state.prefill.aspect);
      setAspect(state.prefill.aspect);
      if (!state.animate) setModelKey("");
    }
    navigate(".", { replace: true, state: null });
  }, [location.state, animate, remix, navigate]);

  const handleFileUpload = async (file: File, isEnd = false) => {
    setUploadError(null);
    if (!file.type.startsWith("image/")) {
      setUploadError("Only image files (PNG, JPG, WebP) are supported.");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setUploadError("File is too large (maximum 20MB).");
      return;
    }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const asset = await api<Asset>("/api/assets/upload", { method: "POST", form: fd });
      if (isEnd) {
        setEndImage(asset);
      } else {
        setStartImage(asset);
        if (!model?.accepts_image) setModelKey("");
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Failed to upload reference image");
    } finally {
      setUploading(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    if (next === "image") setSceneMode("single");
    setModelKey("");
    setTool("single");
    if (next === "image") {
      setStartImage(null);
      setEndImage(null);
    }
  };

  const toggleCompare = (key: string) =>
    setCompareKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : prev.length < MAX_COMPARE ? [...prev, key] : prev));

  const choosePreset = (id: string) => {
    setPresetId(id);
    const wanted = presets.find((p) => p.id === id)?.image_defaults.aspect_ratio;
    if (wanted && ratios.includes(wanted)) setAspect(wanted);
  };

  // Expand prompt handler (P1)
  const handleExpandPrompt = async () => {
    if (!prompt.trim() || expandBusy) return;
    setExpandBusy(true);
    setExpandError(null);
    try {
      const res = await api<{ original: string; expanded: string }>("/api/prompt/expand", {
        method: "POST",
        body: { prompt: prompt.trim(), kind: mode },
      });
      setPreExpandPrompt(prompt);
      setPrompt(res.expanded);
    } catch (err) {
      setExpandError(err instanceof ApiError ? err.message : "Failed to expand prompt");
    } finally {
      setExpandBusy(false);
    }
  };

  const handleUndoExpand = () => {
    if (preExpandPrompt !== null) {
      setPrompt(preExpandPrompt);
      setPreExpandPrompt(null);
    }
  };

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

  const submitStory = async () => {
    if (!provider || !model) return;
    setBusy(true);
    setError(null);
    try {
      const story = await api<Story>("/api/stories", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: { provider: provider.id, model: model.id, aspect_ratio: aspect, size, scenes: trimScenes(scenePrompts), ...(videoRes ? { resolution: videoRes } : {}) },
      });
      trackStory(story);
      void reload();
    } catch (err) {
      setError(err);
      void loadProviders();
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!user) {
      navigate("/auth");
      return;
    }
    if (multi) return submitStory();
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
          count: video || publishOn ? 1 : count,
          preset_id: presetId || null,
          duration: video ? duration : null,
          image_asset_id: video && startImage && model.accepts_image ? startImage.id : null,
          upscale: publishOn ? publishTarget : resolution === "native" ? null : resolution,
          ...(publishOn ? { quality: "publish" } : {}),
          ...(video && videoRes ? { resolution: videoRes } : {}),
        },
      });
      upsertJob(job);
      watch(job.id);
      void reload();
    } catch (err) {
      if (err instanceof ApiError && err.code === "insufficient_credits") {
        setShowBuyCredits(true);
      }
      setError(err);
      void loadProviders();
    } finally {
      setBusy(false);
    }
  };

  const isVideo = mode === "video";
  const activeTool: Tool = isVideo ? "single" : tool;
  const single = activeTool === "single";
  const multi = multiWanted && storyCapable(model);
  const sceneCount = scenePrompts.length;

  const publishOn = publish && !isVideo && single && Boolean(model?.publish_quality);
  const price = priceOf(model, isVideo || publishOn ? 1 : count, publishOn ? publishTarget : resolution, isVideo ? videoRes : null);
  const storyCost = storyPrice(model, sceneCount, videoRes);
  const outSize = expectedDimensions(model, { aspect, size, resolution: videoRes, publish: publishOn, upscale: publishOn ? publishTarget : resolution });
  const outKind = isVideo ? "video/mp4" : "image/webp";
  const outDraft = outSize ? isDraft(outKind, outSize[0], outSize[1]) : false;
  const usdOne = isVideo ? estimatedUsd(model, videoRes, aspect, multi ? STORY_SCENE_SECONDS : duration) : null;
  const usd = usdOne === null ? null : usdOne * (multi ? sceneCount : 1);
  const usdText = usd === null ? null : usdLabel(usd);
  const tier: TierId | null = isVideo ? activeTier(provider?.id, model?.id, videoRes) : null;
  const tierChoices = isVideo ? VIDEO_TIERS.map((t) => ({ tier: t, choice: choices.find(({ p, m }) => p.id === t.provider && m.id === t.model) })).filter((x) => x.choice) : [];

  const pickTier = (id: TierId) => {
    const t = VIDEO_TIERS.find((x) => x.id === id)!;
    setModelKey(`${t.provider}|${t.model}`);
    setVideoRes(t.resolution);
  };

  const togglePublish = (on: boolean) => {
    setPublish(on);
    if (on && publishChoice) {
      setModelKey(`${publishChoice.p.id}|${publishChoice.m.id}`);
      setCount(1);
      setResolution("native");
    }
  };

  const total = multi
    ? storyCost.total
    : activeTool === "compare"
      ? compared.reduce((sum, { m }) => sum + priceOf(m).total, 0)
      : activeTool === "recipe"
        ? priceOf(model).total + priceOf(videoChoice?.m, 1, recipe4k ? "4k" : null).total
        : price.total;

  const hasEnoughCredits = user ? user.credit_balance >= total : true;
  const needsImage = Boolean(model?.requires_image && !startImage);
  const examples = (isVideo ? (["v1", "v2", "v3"] as const) : (["i1", "i2", "i3", "i4"] as const)).map((k) => t(`studio.example_${k}`));

  const canGenerate = multi
    ? !busy && Boolean(provider?.available) && canSubmitStory(scenePrompts)
    : !(busy || prompt.trim().length < 3) &&
    (activeTool === "compare"
      ? compared.length >= 2 && compared.every(({ p }) => p.available)
      : Boolean(provider?.available) && !needsImage && (activeTool !== "recipe" || Boolean(videoChoice)));

  const recent = useMemo(() => {
    const list = [
      ...jobs.map((job) => ({ at: job.created_at, job, kind: job.kind })),
      ...stories.map((story) => ({ at: story.created_at, story, kind: "story" })),
    ].sort((a, b) => b.at.localeCompare(a.at));

    if (historyFilter === "all") return list;
    if (historyFilter === "image") return list.filter((i) => i.kind === "image");
    if (historyFilter === "video") return list.filter((i) => i.kind === "video" || i.kind === "story");
    if (historyFilter === "favorites") {
      return list.filter((i) => {
        if ("job" in i) return i.job.assets.some((a) => a.is_favorite);
        return false;
      });
    }
    return list;
  }, [jobs, stories, historyFilter]);

  const renderStory = (s: Story, i = 0) => (
    <StoryCard
      key={s.id}
      story={s}
      index={i}
      onRetryScene={retryScene}
      onRestitch={restitch}
      onDelete={async (story) => {
        await removeStory(story);
      }}
    />
  );

  const renderCard = (j: Job, i = 0) => (
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
      onEdit={editAsset}
      onUpscale={(a, target) => void upscaleAsset(a, target)}
    />
  );

  return (
    <div className="mx-auto max-w-[1720px] p-3 sm:p-5 lg:p-6">
      {/* 2-Column Responsive Layout */}
      <div className="flex flex-col lg:flex-row items-start gap-5 lg:gap-6">
        {/* LEFT CONTROL PANEL (400-440px on lg+) */}
        <aside
          className="w-full lg:w-[420px] xl:w-[440px] shrink-0 rounded-3xl border border-line bg-surface-1 p-4 sm:p-5 shadow-2xl lg:sticky lg:top-16 lg:max-h-[calc(100vh-5rem)] lg:overflow-y-auto"
          aria-label={t("studio.composer")}
        >
          {/* 1. Mode Tabs */}
          <div className="flex flex-col gap-2.5">
            <Segmented
              label={t("studio.mode")}
              value={mode}
              onChange={switchMode}
              options={[
                { value: "image", label: <span className="flex items-center gap-1.5"><Icon name="image" size={15} />{t("studio.mode_image")}</span> },
                { value: "video", label: <span className="flex items-center gap-1.5"><Icon name="video" size={15} />{t("studio.mode_video")}</span> },
              ]}
            />
            {isVideo && hasStoryModels && (
              <Segmented
                label={t("story.label")}
                value={sceneMode}
                onChange={(next: SceneMode) => {
                  setSceneMode(next);
                  if (next === "multi") setModelKey("");
                }}
                options={[
                  { value: "single", label: t("story.single") },
                  { value: "multi", label: <span className="flex items-center gap-1.5"><Icon name="layers" size={15} />{t("story.multi")}</span> },
                ]}
              />
            )}
            {!isVideo && (
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
            )}
          </div>

          {/* Multi-scene prompts when in multi mode */}
          {multi && (
            <div className="mt-4 flex flex-col gap-2 rounded-2xl border border-line bg-surface-2 p-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-ink">Story scenes ({scenePrompts.length})</span>
                {scenePrompts.length < MAX_SCENES && (
                  <button
                    type="button"
                    onClick={() => setScenePrompts(addScene(scenePrompts))}
                    className="text-xs text-accent hover:underline font-medium"
                  >
                    + Add scene
                  </button>
                )}
              </div>
              {scenePrompts.map((sp, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="font-mono text-xs text-muted w-5">#{idx + 1}</span>
                  <input
                    type="text"
                    value={sp}
                    onChange={(e) => {
                      const next = [...scenePrompts];
                      next[idx] = e.target.value;
                      setScenePrompts(next);
                    }}
                    placeholder={`Scene ${idx + 1} action...`}
                    className="flex-1 rounded-xl border border-line bg-surface-3 px-3 py-1.5 text-xs text-ink placeholder:text-muted/50 focus:border-accent/60 focus:outline-none"
                  />
                  {scenePrompts.length > MIN_SCENES && (
                    <button
                      type="button"
                      onClick={() => setScenePrompts(removeScene(scenePrompts, idx))}
                      className="text-muted hover:text-danger text-sm px-1"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Compare tool configuration */}
          {activeTool === "compare" && !isVideo && (
            <div className="mt-4 rounded-2xl border border-line bg-surface-2 p-3 text-xs">
              <p className="font-semibold text-ink">Select models to compare (2 to {MAX_COMPARE})</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {imageChoices.map(({ p, m }) => {
                  const key = `${p.id}|${m.id}`;
                  const on = compareKeys.includes(key);
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => toggleCompare(key)}
                      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition ${
                        on ? "border-accent bg-accent/20 text-accent font-semibold" : "border-line text-muted hover:text-ink"
                      }`}
                    >
                      {m.label} ({priceOf(m).total} cr)
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* 2. Reference Dropzones (Image input / start frame & optional end frame) */}
          {isVideo && !multi && (
            <div className="mt-4 flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-ink">Reference frames</span>
                {startImage && (
                  <button
                    type="button"
                    onClick={() => { setStartImage(null); setEndImage(null); }}
                    className="text-[11px] text-muted hover:text-danger transition"
                  >
                    Clear all
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {/* Start Frame */}
                <div
                  onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                    const file = e.dataTransfer.files[0];
                    if (file) void handleFileUpload(file, false);
                  }}
                  className={`relative flex min-h-[96px] flex-col items-center justify-center rounded-2xl border border-dashed p-2 text-center transition ${
                    startImage
                      ? "border-line bg-surface-2"
                      : dragging
                      ? "border-accent bg-accent/10"
                      : "border-line/70 bg-surface-2/40 hover:border-white/20"
                  }`}
                >
                  {startImage ? (
                    <div className="relative h-full w-full">
                      <img src={startImage.preview_url || startImage.url} alt="Start frame" className="h-20 w-full rounded-xl object-cover" />
                      <button
                        type="button"
                        onClick={() => setStartImage(null)}
                        className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-black/70 text-ink hover:text-danger"
                      >
                        <Icon name="close" size={11} />
                      </button>
                      <span className="absolute bottom-1 left-1 rounded bg-black/60 px-1 py-0.5 text-[9px] font-mono text-ink">Start</span>
                    </div>
                  ) : (
                    <label className="flex cursor-pointer flex-col items-center gap-1">
                      <Icon name="image" size={18} className="text-muted" />
                      <span className="text-[11px] font-medium text-ink">Start frame</span>
                      <span className="text-[9px] text-muted">{uploading ? "Uploading..." : "Click or drop"}</span>
                      <input type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && void handleFileUpload(e.target.files[0], false)} className="sr-only" />
                    </label>
                  )}
                </div>

                {/* Optional End Frame */}
                <div
                  className={`relative flex min-h-[96px] flex-col items-center justify-center rounded-2xl border border-dashed p-2 text-center transition ${
                    endImage ? "border-line bg-surface-2" : "border-line/70 bg-surface-2/40 hover:border-white/20"
                  }`}
                >
                  {endImage ? (
                    <div className="relative h-full w-full">
                      <img src={endImage.preview_url || endImage.url} alt="End frame" className="h-20 w-full rounded-xl object-cover" />
                      <button
                        type="button"
                        onClick={() => setEndImage(null)}
                        className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-black/70 text-ink hover:text-danger"
                      >
                        <Icon name="close" size={11} />
                      </button>
                      <span className="absolute bottom-1 left-1 rounded bg-black/60 px-1 py-0.5 text-[9px] font-mono text-ink">End</span>
                    </div>
                  ) : (
                    <label className="flex cursor-pointer flex-col items-center gap-1">
                      <Icon name="image" size={18} className="text-muted/60" />
                      <span className="text-[11px] font-medium text-muted">End frame</span>
                      <span className="text-[9px] text-muted">Optional</span>
                      <input type="file" accept="image/*" onChange={(e) => e.target.files?.[0] && void handleFileUpload(e.target.files[0], true)} className="sr-only" />
                    </label>
                  )}
                </div>
              </div>
              {uploadError && <p className="text-[11px] text-danger">{uploadError}</p>}
            </div>
          )}

          {/* 3. Prompt Card */}
          <div className="mt-4 rounded-2xl border border-line bg-surface-2 p-3.5">
            <div className="flex items-center justify-between text-xs text-muted mb-1.5">
              <label htmlFor="prompt" className="font-semibold text-ink">
                {t("studio.prompt")}
              </label>
              <div className="flex items-center gap-2">
                <VoiceButton
                  onText={(text: string) => setPrompt((p) => (p.trim() ? `${p.trim()} ${text}` : text))}
                  onError={() => {}}
                />
                <span className="font-mono text-[10px] tabular-nums">
                  {prompt.length}/{MAX_PROMPT}
                </span>
              </div>
            </div>

            <textarea
              id="prompt"
              rows={3}
              value={prompt}
              maxLength={MAX_PROMPT}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={mode === "video" ? "A futuristic neon city with flying cars in rain, cinematic lighting..." : "A cozy Scandinavian living room with morning sunlight..."}
              className="w-full resize-none bg-transparent text-sm leading-relaxed text-ink placeholder:text-muted/50 focus:outline-none"
            />

            {/* Prompt Actions Bar */}
            <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-line/60 pt-2">
              <div className="flex flex-wrap items-center gap-1.5">
                {/* Expand Prompt (P1) */}
                <button
                  type="button"
                  onClick={() => void handleExpandPrompt()}
                  disabled={!prompt.trim() || expandBusy}
                  className="inline-flex items-center gap-1 rounded-lg border border-accent/30 bg-accent/10 px-2.5 py-1 text-[11px] font-semibold text-accent transition hover:border-accent hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
                  title="Expand prompt into a rich cinematic description"
                >
                  <Icon name="sparkle" size={12} className={expandBusy ? "animate-spin" : ""} />
                  {expandBusy ? "Expanding..." : "Expand prompt"}
                </button>
                {preExpandPrompt !== null && (
                  <button
                    type="button"
                    onClick={handleUndoExpand}
                    className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-[11px] text-muted hover:text-ink transition"
                    title="Undo prompt expansion"
                  >
                    Undo
                  </button>
                )}
                {isVideo && model?.has_audio && (
                  <button
                    type="button"
                    onClick={() => setPrompt((p) => (p.trim() ? `${p.trim()} with realistic ambient sound` : "with realistic ambient sound"))}
                    className="inline-flex items-center gap-1 rounded-lg border border-line bg-surface-3 px-2 py-1 text-[11px] text-muted hover:text-accent transition"
                  >
                    <Icon name="sound" size={12} />
                    Audio
                  </button>
                )}
              </div>
            </div>

            {expandError && <p className="mt-2 text-[11px] text-danger">{expandError}</p>}
          </div>

          {/* Example prompt chips */}
          {prompt.trim() === "" && (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {examples.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setPrompt(ex)}
                  className="max-w-full truncate rounded-xl border border-line bg-surface-2/60 px-2.5 py-1 text-left text-[11px] text-muted transition hover:border-white/20 hover:text-ink"
                >
                  {ex}
                </button>
              ))}
            </div>
          )}

          {/* Presets Row */}
          {presets.length > 0 && !multi && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-muted mb-1.5">
                <span className="font-medium text-muted">Presets</span>
                {presetId && (
                  <button type="button" onClick={() => setPresetId("")} className="text-[11px] text-accent hover:underline">
                    Clear
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {presets.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => choosePreset(p.id)}
                    className={`rounded-xl border px-2.5 py-1 text-[11px] transition ${
                      presetId === p.id ? "border-accent bg-accent/15 text-accent font-semibold" : "border-line bg-surface-2 text-muted hover:text-ink"
                    }`}
                  >
                    {t(`presets.${p.id}.name`, { defaultValue: p.id })}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 4. Model Row (click opens ModelPicker modal) */}
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setPicking(true)}
              className="group flex w-full items-center justify-between gap-3 rounded-2xl border border-line bg-surface-2 p-3 text-left transition hover:border-accent/50 hover:bg-surface-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <ModelSwatch seed={modelKey || "default"} size={36} provider={provider?.id} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-xs font-semibold text-ink group-hover:text-accent transition">
                      {model?.label || t("studio.pickModel")}
                    </p>
                    {provider?.tier && (
                      <Badge tone={provider.tier === "free" ? "free" : "paid"}>
                        {provider.tier === "free" ? t("studio.free") : t("studio.paid")}
                      </Badge>
                    )}
                    {model?.commercial_use === "byok_only" && <Badge tone="muted">BYOK</Badge>}
                  </div>
                  <p className="truncate text-[11px] text-muted">
                    {provider?.name || "Select AI Model"} · {onFreeShare(provider) ? "Free" : usdText?.short ? `≈ ${usdText.short}` : `${price.total} credits`}
                  </p>
                </div>
              </div>
              <span className="rounded-lg border border-line bg-surface-1 px-2.5 py-1 text-[11px] font-medium text-muted group-hover:border-accent/40 group-hover:text-ink transition shrink-0">
                Change
              </span>
            </button>
          </div>

          {/* 5. Setting Tiles in a 2-Column Grid (Duration, Aspect, Resolution, Quality) */}
          <div className="mt-4 grid grid-cols-2 gap-2.5">
            {/* Aspect Ratio Tile */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setActivePopover((v) => (v === "aspect" ? null : "aspect"))}
                className="flex w-full flex-col gap-1 rounded-2xl border border-line bg-surface-2 p-2.5 text-left transition hover:border-white/20"
              >
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted">Aspect Ratio</span>
                <span className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                  <Icon name="ratio" size={14} className="text-accent" />
                  {aspect}
                </span>
              </button>

              {activePopover === "aspect" && (
                <div className="absolute left-0 top-full z-20 mt-1.5 w-48 rounded-2xl border border-line bg-surface-1 p-2 shadow-2xl backdrop-blur-md">
                  <div className="grid grid-cols-2 gap-1">
                    {ratios.map((r) => (
                      <button
                        key={r}
                        type="button"
                        onClick={() => {
                          setAspect(r);
                          setActivePopover(null);
                        }}
                        className={`flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-xs font-medium transition ${
                          aspect === r ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface-2 hover:text-ink"
                        }`}
                      >
                        <span
                          className="border border-current rounded-[2px]"
                          style={{
                            width: r === "16:9" ? 14 : r === "9:16" ? 8 : r === "4:3" ? 12 : r === "3:4" ? 9 : 10,
                            height: r === "9:16" ? 14 : r === "3:4" ? 12 : 10,
                          }}
                        />
                        {r}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Duration Tile (Video) or Batch Count (Image) */}
            {isVideo ? (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setActivePopover((v) => (v === "duration" ? null : "duration"))}
                  className="flex w-full flex-col gap-1 rounded-2xl border border-line bg-surface-2 p-2.5 text-left transition hover:border-white/20"
                >
                  <span className="text-[10px] font-medium uppercase tracking-wider text-muted">Duration</span>
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                    <Icon name="clock" size={14} className="text-accent" />
                    {duration ? `${duration}s` : "Default"}
                  </span>
                </button>

                {activePopover === "duration" && model?.durations?.length && (
                  <div className="absolute right-0 top-full z-20 mt-1.5 w-40 rounded-2xl border border-line bg-surface-1 p-2 shadow-2xl backdrop-blur-md">
                    <div className="flex flex-col gap-1">
                      {model.durations.map((d) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => {
                            setDuration(d);
                            setActivePopover(null);
                          }}
                          className={`flex items-center justify-between rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                            duration === d ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface-2 hover:text-ink"
                          }`}
                        >
                          <span>{d} seconds</span>
                          {duration === d && <Icon name="check" size={13} />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-1 rounded-2xl border border-line bg-surface-2 p-2.5">
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted">Outputs</span>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-ink">{count}× image</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={count <= 1}
                      onClick={() => setCount((c) => Math.max(1, c - 1))}
                      className="grid h-5 w-5 place-items-center rounded bg-surface-3 text-xs text-muted hover:text-ink disabled:opacity-40"
                    >
                      -
                    </button>
                    <span className="w-4 text-center font-mono text-xs">{count}</span>
                    <button
                      type="button"
                      disabled={count >= (model?.max_count ?? 4)}
                      onClick={() => setCount((c) => Math.min(model?.max_count ?? 4, c + 1))}
                      className="grid h-5 w-5 place-items-center rounded bg-surface-3 text-xs text-muted hover:text-ink disabled:opacity-40"
                    >
                      +
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Resolution Tile */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setActivePopover((v) => (v === "resolution" ? null : "resolution"))}
                className="flex w-full flex-col gap-1 rounded-2xl border border-line bg-surface-2 p-2.5 text-left transition hover:border-white/20"
              >
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted">Resolution</span>
                <span className="flex items-center gap-1.5 text-xs font-semibold text-ink">
                  <Icon name="wand" size={14} className="text-accent" />
                  {isVideo ? videoRes || "Auto" : resolution === "native" ? "Native" : resolution.toUpperCase()}
                  {((isVideo && videoRes === "480p") || outDraft) && (
                    <span className="rounded bg-accent-3/20 px-1 py-0.2 text-[9px] font-bold text-accent-3">Draft</span>
                  )}
                </span>
              </button>

              {activePopover === "resolution" && (
                <div className="absolute left-0 top-full z-20 mt-1.5 w-48 rounded-2xl border border-line bg-surface-1 p-2 shadow-2xl backdrop-blur-md">
                  <div className="flex flex-col gap-1">
                    {isVideo && model?.resolutions?.length
                      ? model.resolutions.map((r) => (
                          <button
                            key={r}
                            type="button"
                            onClick={() => {
                              setVideoRes(r);
                              setActivePopover(null);
                            }}
                            className={`flex items-center justify-between rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                              videoRes === r ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface-2 hover:text-ink"
                            }`}
                          >
                            <span>{r}</span>
                            {r === "480p" && <span className="text-[10px] text-accent-3">Draft</span>}
                            {videoRes === r && <Icon name="check" size={13} />}
                          </button>
                        ))
                      : (["native", ...(model?.upscale_targets ?? [])] as const).map((r) => (
                          <button
                            key={r}
                            type="button"
                            onClick={() => {
                              setResolution(r);
                              setActivePopover(null);
                            }}
                            className={`flex items-center justify-between rounded-xl px-3 py-1.5 text-xs font-medium transition ${
                              resolution === r ? "bg-accent/15 text-accent" : "text-muted hover:bg-surface-2 hover:text-ink"
                            }`}
                          >
                            <span>{r === "native" ? "Native" : r.toUpperCase()}</span>
                            {resolution === r && <Icon name="check" size={13} />}
                          </button>
                        ))}
                  </div>
                </div>
              )}
            </div>

            {/* Quality Tier Tile (Video) or Publish Quality (Image) */}
            {isVideo && tierChoices.length > 0 ? (
              <div className="flex flex-col gap-1 rounded-2xl border border-line bg-surface-2 p-2.5">
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted">Tier</span>
                <select
                  value={(tier ?? "") as TierId}
                  onChange={(e) => pickTier(e.target.value as TierId)}
                  className="cursor-pointer appearance-none bg-transparent text-xs font-semibold text-ink focus:outline-none"
                >
                  {tierChoices.map(({ tier: x }) => (
                    <option key={x.id} value={x.id} className="bg-surface-1 text-ink">
                      {t(`studio.tier_${x.id}`)}
                    </option>
                  ))}
                </select>
              </div>
            ) : publishChoice ? (
              <div className="flex items-center justify-between rounded-2xl border border-line bg-surface-2 p-2.5">
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted">Publish 2K</span>
                <button
                  type="button"
                  aria-pressed={publishOn}
                  onClick={() => togglePublish(!publishOn)}
                  className={`rounded-lg px-2 py-1 text-xs font-semibold transition ${
                    publishOn ? "bg-accent text-black" : "border border-line text-muted hover:text-ink"
                  }`}
                >
                  {publishOn ? "ON" : "OFF"}
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-1 rounded-2xl border border-line bg-surface-2 p-2.5 opacity-60">
                <span className="text-[10px] font-medium uppercase tracking-wider text-muted">Quality</span>
                <span className="text-xs font-semibold text-ink">Standard</span>
              </div>
            )}
          </div>

          {/* 6. Sticky Bottom Action Bar */}
          <div className="sticky bottom-0 -mx-4 -mb-4 sm:-mx-5 sm:-mb-5 mt-5 rounded-b-3xl border-t border-line bg-surface-1/95 p-4 backdrop-blur-md z-10">
            <Button
              className="w-full py-3 text-sm font-semibold tracking-wide shadow-lg"
              disabled={Boolean(user && !canGenerate)}
              onClick={() => void submit()}
            >
              <Icon name="sparkle" size={17} />
              {busy
                ? t("studio.generating")
                : !user
                ? "Sign in to generate"
                : !hasEnoughCredits
                ? "Get credits"
                : multi
                ? t("story.generate", { n: sceneCount })
                : activeTool === "compare"
                ? t("compare.send", { count: compared.length })
                : `Generate · ${usdText?.short ? `≈ ${usdText.short}` : `${total} credits`}`}
            </Button>

            {/* Cost and Status Footer Line */}
            <div className="mt-2.5 flex items-center justify-between text-[11px] text-muted">
              <span className="font-mono">
                {usdText ? t("price.usdEstimate", { amount: usdText.short }) : `${total} credits`}
                {onFreeShare(provider) && <span className="ml-1 text-ok">· Free</span>}
              </span>
              {provider && <QuotaLine provider={provider} />}
            </div>

            <ErrorText error={error} />
          </div>
        </aside>

        {/* RIGHT CANVAS: Toolbar + History / How it works */}
        <main className="flex-1 min-w-0 rounded-3xl border border-line bg-surface-1/40 p-4 sm:p-6 min-h-[600px] flex flex-col">
          {/* Top Canvas Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4 mb-5">
            <div className="flex items-center gap-2">
              <Segmented
                label="Canvas views"
                value={canvasTab}
                onChange={setCanvasTab}
                options={[
                  { value: "history", label: <span className="flex items-center gap-1.5"><Icon name="history" size={15} />History ({recent.length})</span> },
                  { value: "how-it-works", label: <span className="flex items-center gap-1.5"><Icon name="sparkle" size={15} />How it works</span> },
                ]}
              />
            </div>

            {/* History Controls Toolbar */}
            {canvasTab === "history" && (
              <div className="flex items-center gap-2 text-xs">
                {/* Filter Selector */}
                <select
                  value={historyFilter}
                  onChange={(e) => setHistoryFilter(e.target.value as typeof historyFilter)}
                  className="rounded-xl border border-line bg-surface-2 px-3 py-1.5 text-xs text-muted hover:text-ink focus:outline-none"
                >
                  <option value="all">All types</option>
                  <option value="image">Images</option>
                  <option value="video">Videos</option>
                  <option value="favorites">Favorites</option>
                </select>

                {/* Grid Density Slider / Button */}
                <div className="hidden sm:flex items-center gap-1 rounded-xl border border-line bg-surface-2 p-1">
                  {([2, 3, 4] as const).map((cols) => (
                    <button
                      key={cols}
                      type="button"
                      onClick={() => setGridCols(cols)}
                      className={`grid h-6 w-6 place-items-center rounded-lg text-xs font-mono transition ${
                        gridCols === cols ? "bg-accent/20 text-accent font-bold" : "text-muted hover:text-ink"
                      }`}
                      title={`${cols} columns`}
                    >
                      {cols}
                    </button>
                  ))}
                </div>

                {/* List / Grid Toggle */}
                <button
                  type="button"
                  onClick={() => setIsListView((v) => !v)}
                  className="grid h-8 w-8 place-items-center rounded-xl border border-line bg-surface-2 text-muted hover:text-ink transition"
                  title={isListView ? "Grid view" : "List view"}
                >
                  <Icon name={isListView ? "layers" : "image"} size={14} />
                </button>
              </div>
            )}
          </div>

          {/* Comparison Run Block (when tool === "compare" and run exists) */}
          {compareRun && compareRun.length > 0 && (
            <div className="mb-6 rounded-2xl border border-line bg-surface-2/60 p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink">Compare Results</h3>
                <button type="button" onClick={() => setCompareRun(null)} className="text-xs text-muted hover:text-ink">
                  Close
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {compareRun.map((c) => {
                  const job = jobs.find((j) => j.id === c.jobId);
                  const asset = job?.assets[0];
                  return (
                    <figure key={c.key} className="overflow-hidden rounded-xl border border-line bg-surface-3 p-2">
                      <div className="aspect-square rounded-lg bg-surface-1 grid place-items-center overflow-hidden">
                        {asset ? (
                          <img src={asset.preview_url || asset.url} alt="" className="h-full w-full object-cover" />
                        ) : (
                          <span className="text-[10px] text-muted">{job ? job.status : "Queued"}</span>
                        )}
                      </div>
                      <figcaption className="mt-2 text-[11px]">
                        <p className="truncate font-semibold text-ink">{c.label}</p>
                        <p className="text-muted">{c.cost} credits</p>
                      </figcaption>
                    </figure>
                  );
                })}
              </div>
            </div>
          )}

          {/* Canvas Content */}
          {canvasTab === "how-it-works" || recent.length === 0 ? (
            /* How It Works / Empty State: 3 Step Cards */
            <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
              <span className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3.5 py-1 text-xs font-semibold text-accent">
                <Icon name="sparkle" size={13} />
                Studio Quickstart
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">Create AI Videos & Images in Seconds</h2>
              <p className="mt-2 max-w-lg text-sm text-muted">
                Turn your imagination into high-fidelity generative media with leading OpenRouter and frontier AI models.
              </p>

              <div className="mt-8 grid gap-4 sm:grid-cols-3 max-w-4xl w-full text-left">
                {/* Step 1 */}
                <div className="rounded-2xl border border-line bg-surface-2/60 p-5 flex flex-col justify-between">
                  <div>
                    <span className="rounded-lg bg-surface-3 px-2 py-0.5 font-mono text-[11px] font-semibold text-accent">
                      STEP 1
                    </span>
                    <h3 className="mt-3 text-base font-semibold text-ink">Describe or Upload</h3>
                    <p className="mt-1.5 text-xs text-muted leading-relaxed">
                      Type your scene prompt or upload a reference starting image. Use "Expand prompt" for instant cinematic enhancement.
                    </p>
                  </div>
                </div>

                {/* Step 2 */}
                <div className="rounded-2xl border border-line bg-surface-2/60 p-5 flex flex-col justify-between">
                  <div>
                    <span className="rounded-lg bg-surface-3 px-2 py-0.5 font-mono text-[11px] font-semibold text-accent">
                      STEP 2
                    </span>
                    <h3 className="mt-3 text-base font-semibold text-ink">Choose AI Model</h3>
                    <p className="mt-1.5 text-xs text-muted leading-relaxed">
                      Pick from Seedance 2.5, FLUX.1, Wan 2.1, Kling, or connect your own OpenRouter key. Fine-tune aspect ratio and resolution.
                    </p>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="rounded-2xl border border-line bg-surface-2/60 p-5 flex flex-col justify-between">
                  <div>
                    <span className="rounded-lg bg-surface-3 px-2 py-0.5 font-mono text-[11px] font-semibold text-accent">
                      STEP 3
                    </span>
                    <h3 className="mt-3 text-base font-semibold text-ink">Generate & Enhance</h3>
                    <p className="mt-1.5 text-xs text-muted leading-relaxed">
                      Hit Generate. Watch live rendering in your canvas, then upscale to 4K, animate images into clips, or download.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Results Grid */
            <div
              className={`grid gap-4 ${
                isListView
                  ? "grid-cols-1"
                  : gridCols === 2
                  ? "grid-cols-1 sm:grid-cols-2"
                  : gridCols === 3
                  ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
                  : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
              }`}
            >
              {recent.map((item, i) =>
                "story" in item ? renderStory(item.story, i) : renderCard(item.job, i)
              )}
            </div>
          )}
        </main>
      </div>

      {/* Model Picker Modal */}
      {picking && (
        <ModelPicker
          choices={choices}
          inactive={inactiveModels}
          value={modelKey}
          mode={mode}
          onSelect={setModelKey}
          onClose={closePicker}
          count={isVideo ? 1 : count}
          upscale={resolution === "native" ? undefined : resolution}
        />
      )}

      {/* Buy Credits Modal */}
      {showBuyCredits && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="relative w-full max-w-md rounded-3xl border border-line bg-surface-1 p-6 shadow-2xl">
            <button
              type="button"
              onClick={() => setShowBuyCredits(false)}
              className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-xl text-muted hover:bg-white/[0.06] hover:text-ink"
            >
              <Icon name="close" size={16} />
            </button>
            <h2 className="text-xl font-bold">Credits Needed</h2>
            <p className="mt-1 text-xs text-muted">Purchase credit packs to continue generating high-resolution videos and images.</p>
            <div className="mt-4">
              <BuyCredits onPaid={() => { setShowBuyCredits(false); void reload(); }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
