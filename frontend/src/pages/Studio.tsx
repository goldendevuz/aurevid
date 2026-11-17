// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import JobCard from "../components/JobCard";
import { Badge, Button, Card, ErrorText, inputClass, Label } from "../components/ui";
import type { Job, Preset, Provider } from "../types";

const MAX_PROMPT = 1000;
const SIZES = ["small", "medium", "large"] as const;

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
    timer = setTimeout(poll, 2000);
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

export default function Studio() {
  const { t } = useTranslation();
  const { reload } = useAuth();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [prompt, setPrompt] = useState("");
  const [modelKey, setModelKey] = useState("");
  const [aspect, setAspect] = useState("1:1");
  const [size, setSize] = useState<(typeof SIZES)[number]>("large");
  const [count, setCount] = useState(1);
  const [presetId, setPresetId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const watchers = useRef(new Map<string, () => void>());

  const upsertJob = useCallback((job: Job) => {
    setJobs((prev) => {
      const rest = prev.filter((j) => j.id !== job.id);
      return [job, ...rest].sort((a, b) => b.created_at.localeCompare(a.created_at));
    });
    if (job.status === "done" || job.status === "failed") {
      watchers.current.get(job.id)?.();
      watchers.current.delete(job.id);
      void reload(); // refresh credit balance (refunds)
    }
  }, [reload]);

  const watch = useCallback((id: string) => {
    if (!watchers.current.has(id)) watchers.current.set(id, watchJob(id, upsertJob));
  }, [upsertJob]);

  useEffect(() => {
    void (async () => {
      const [p, pr, recent] = await Promise.all([
        api<Provider[]>("/api/providers"),
        api<Preset[]>("/api/presets"),
        api<Job[]>("/api/jobs?limit=12"),
      ]);
      setProviders(p);
      setPresets(pr);
      setJobs(recent);
      const first = p.find((x) => x.available);
      if (first) setModelKey(`${first.id}|${first.models[0].id}`);
      recent.filter((j) => j.status === "queued" || j.status === "running").forEach((j) => watch(j.id));
    })().catch(setError);
    const current = watchers.current;
    return () => current.forEach((stop) => stop());
  }, [watch]);

  const [providerId, modelId] = modelKey.split("|");
  const provider = providers.find((p) => p.id === providerId);
  const model = provider?.models.find((m) => m.id === modelId);
  const ratios = useMemo(() => model?.aspect_ratios ?? ["1:1"], [model]);

  useEffect(() => {
    if (!ratios.includes(aspect)) setAspect(ratios[0]);
  }, [ratios, aspect]);

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
      const job = await api<Job>("/api/jobs", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: {
          prompt,
          provider: provider.id,
          model: model.id,
          aspect_ratio: aspect,
          size,
          count,
          preset_id: presetId || null,
        },
      });
      upsertJob(job);
      watch(job.id);
      void reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const cost = (model?.credit_cost ?? 1) * count;

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Card className="h-fit lg:sticky lg:top-6">
        <Label htmlFor="prompt">{t("studio.promptLabel")}</Label>
        <textarea
          id="prompt"
          rows={5}
          maxLength={MAX_PROMPT}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={t("studio.promptPlaceholder")}
          className={`${inputClass} resize-y`}
        />
        <p className="mt-1 text-right text-[11px] text-muted">
          {t("studio.chars", { count: prompt.length, max: MAX_PROMPT })}
        </p>

        <div className="mt-4">
          <Label htmlFor="model">{t("studio.model")}</Label>
          <select id="model" value={modelKey} onChange={(e) => setModelKey(e.target.value)} className={inputClass}>
            {providers.map((p) => (
              <optgroup key={p.id} label={`${p.name} · ${p.tier === "free" ? t("studio.free") : t("studio.paid")}`}>
                {p.models.map((m) => (
                  <option key={m.id} value={`${p.id}|${m.id}`} disabled={!p.available}>
                    {m.label}
                    {!p.available ? ` (${t("studio.needsKey")})` : ""}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {provider && model && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone={provider.tier === "free" ? "free" : "paid"}>
                {provider.tier === "free" ? t("studio.free") : t("studio.paid")}
              </Badge>
              {provider.key_source === "user" && <Badge tone="muted">{t("studio.byok")}</Badge>}
              <Badge tone={model.commercial_use === "yes" ? "ok" : "muted"}>
                {t(`studio.commercial_${model.commercial_use}`)}
              </Badge>
            </div>
          )}
          {providers.some((p) => !p.available) && (
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
          <div>
            <Label htmlFor="count">{t("studio.count")}</Label>
            <select id="count" value={count} onChange={(e) => setCount(Number(e.target.value))} className={inputClass}>
              {[1, 2, 3, 4].slice(0, model?.max_count ?? 4).map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        </div>

        <Button
          className="mt-5 w-full"
          disabled={busy || prompt.trim().length < 3 || !provider?.available}
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
              <JobCard key={j.id} job={j} onChange={upsertJob} onReuse={setPrompt} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
