// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import JobCard from "../components/JobCard";
import { Icon } from "../components/icons";
import { Button, EmptyState, ErrorText, PageHeader, Segmented, inputClass } from "../components/ui";
import { isFinished, retryJob, watchJob } from "../jobs";
import type { Job, JobFacets } from "../types";

const PAGE = 20;
const KINDS = ["image", "video", "upscale"] as const;
const STATUSES = ["done", "failed", "active"] as const;
const PERIODS = ["today", "7d", "30d"] as const;
// URL query keys (also the API's), so a filtered view can be bookmarked or shared.
const FILTER_KEYS = ["kind", "status", "provider", "model", "period", "q", "favorites", "hide_failed"] as const;

const selectClass = `${inputClass} !w-auto min-w-0 max-w-full py-2 pr-8`;
const toggleClass = (on: boolean) =>
  `inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-45 ${
    on ? "border-accent/60 bg-accent/15 text-white" : "border-line bg-bg/60 text-muted hover:text-ink"
  }`;

export default function History() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { reload: reloadCredits } = useAuth();
  const [params, setParams] = useSearchParams();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [facets, setFacets] = useState<JobFacets | null>(null);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [query, setQuery] = useState(() => params.get("q") ?? "");
  const request = useRef(0);
  const watchers = useRef(new Map<string, () => void>());

  const get = (key: (typeof FILTER_KEYS)[number]) => params.get(key) ?? "";
  const kind = get("kind");
  const status = get("status");
  const provider = get("provider");
  const model = get("model");
  const period = get("period");
  const favorites = get("favorites") === "true";
  const hideFailed = get("hide_failed") === "true";
  const anyFilter = FILTER_KEYS.some((k) => params.has(k));

  const setFilter = useCallback(
    (changes: Partial<Record<(typeof FILTER_KEYS)[number], string | boolean>>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(changes)) {
            if (v === "" || v === false) next.delete(k);
            else next.set(k, String(v));
          }
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  // Debounce typing into the URL (and so into the request).
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed === (params.get("q") ?? "")) return;
    const id = setTimeout(() => setFilter({ q: trimmed }), 300);
    return () => clearTimeout(id);
  }, [query, params, setFilter]);

  // Only the known filter keys reach the API, in a stable order.
  const apiQuery = useMemo(() => {
    const q = new URLSearchParams();
    for (const k of FILTER_KEYS) {
      const v = params.get(k);
      if (v) q.set(k, v);
    }
    return q.toString();
  }, [params]);

  const onUpdate = useCallback((job: Job) => {
    setJobs((prev) => prev.map((x) => (x.id === job.id ? job : x)));
    if (isFinished(job)) {
      watchers.current.get(job.id)?.();
      watchers.current.delete(job.id);
    }
  }, []);

  const watchPending = useCallback(
    (list: Job[]) =>
      list
        .filter((j) => !isFinished(j) && !watchers.current.has(j.id))
        .forEach((j) => watchers.current.set(j.id, watchJob(j.id, onUpdate))),
    [onUpdate],
  );

  const loadFacets = useCallback(() => api<JobFacets>("/api/jobs/facets").then(setFacets), []);

  const load = useCallback(
    async (before?: string) => {
      const id = ++request.current;
      const q = new URLSearchParams(apiQuery);
      q.set("limit", String(PAGE));
      if (before) q.set("before", before);
      setLoading(true);
      try {
        const page = await api<Job[]>(`/api/jobs?${q}`);
        if (id !== request.current) return; // a newer filter won
        setJobs((prev) => (before ? [...prev, ...page] : page));
        setMore(page.length === PAGE);
        setError(null);
        watchPending(page);
      } finally {
        if (id === request.current) setLoading(false);
      }
    },
    [apiQuery, watchPending],
  );

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  useEffect(() => {
    loadFacets().catch(setError);
    const current = watchers.current;
    return () => current.forEach((stop) => stop());
  }, [loadFacets]);

  const retry = async (job: Job) => {
    const created = await retryJob(job);
    setJobs((prev) => [created, ...prev.filter((x) => x.id !== created.id)]);
    watchPending([created]);
    void reloadCredits();
    void loadFacets();
  };

  const remove = async (job: Job) => {
    await api(`/api/jobs/${job.id}`, { method: "DELETE" });
    setJobs((prev) => prev.filter((x) => x.id !== job.id));
    void loadFacets();
  };

  const clearAll = () => {
    setQuery("");
    setParams(new URLSearchParams(), { replace: true });
  };

  const count = (list: JobFacets["kinds"] | undefined, value: string) => list?.find((f) => f.value === value)?.count ?? 0;
  const withCount = (label: string, n: number | undefined) => (facets && n !== undefined ? `${label} · ${n}` : label);
  const providerLabel = (value: string, label?: string | null) => (value === "local" ? t("history.localUpscaler") : (label ?? value));
  const models = (facets?.models ?? []).filter((m) => !provider || m.provider === provider);
  const kinds = KINDS.filter((k) => k !== "upscale" || count(facets?.kinds, k) > 0 || kind === k);

  return (
    <div>
      <PageHeader
        title={t("history.title")}
        subtitle={facets ? t("history.total", { count: facets.total }) : undefined}
        actions={
          <Segmented
            label={t("history.title")}
            value={favorites ? "fav" : "all"}
            onChange={(v) => setFilter({ favorites: v === "fav" })}
            options={[
              { value: "all", label: t("history.all") },
              { value: "fav", label: <span className="flex items-center gap-1.5"><Icon name="star" size={14} />{t("history.favorites")}</span> },
            ]}
          />
        }
      />

      <section role="search" aria-label={t("history.filters")} className="glass mb-6 space-y-3 rounded-[var(--radius-card)] p-4">
        <div className="flex flex-wrap gap-2">
          <label className="relative min-w-0 flex-1 basis-56">
            <span className="sr-only">{t("history.search")}</span>
            <Icon name="search" size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              type="search"
              value={query}
              maxLength={200}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("history.searchPlaceholder")}
              className={`${inputClass} py-2 pl-9`}
            />
          </label>
          <select aria-label={t("history.period")} value={period} onChange={(e) => setFilter({ period: e.target.value })} className={selectClass}>
            <option value="">{t("history.period_all")}</option>
            {PERIODS.map((p) => (
              <option key={p} value={p}>{t(`history.period_${p}`)}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap gap-2">
          <Segmented
            label={t("history.kind")}
            value={kind}
            onChange={(v) => setFilter({ kind: v })}
            className="max-w-full overflow-x-auto"
            options={[
              { value: "", label: t("history.anyKind") },
              ...kinds.map((k) => ({ value: k, label: withCount(t(`history.kind_${k}`), count(facets?.kinds, k)) })),
            ]}
          />
          <Segmented
            label={t("history.status")}
            value={status}
            onChange={(v) => setFilter({ status: v })}
            className="max-w-full overflow-x-auto"
            options={[
              { value: "", label: t("history.anyStatus") },
              ...STATUSES.map((s) => ({ value: s, label: withCount(t(`history.status_${s}`), count(facets?.statuses, s)) })),
            ]}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label={t("history.provider")}
            value={provider}
            onChange={(e) => {
              const next = e.target.value;
              const keepModel = !next || facets?.models.some((m) => m.value === model && m.provider === next);
              setFilter({ provider: next, ...(keepModel ? {} : { model: "" }) });
            }}
            className={selectClass}
          >
            <option value="">{t("history.anyProvider")}</option>
            {facets?.providers.map((p) => (
              <option key={p.value} value={p.value}>{withCount(providerLabel(p.value, p.label), p.count)}</option>
            ))}
          </select>
          <select aria-label={t("history.model")} value={model} onChange={(e) => setFilter({ model: e.target.value })} className={selectClass}>
            <option value="">{t("history.anyModel")}</option>
            {models.map((m) => (
              <option key={`${m.provider}|${m.value}`} value={m.value}>{withCount(m.label ?? m.value, m.count)}</option>
            ))}
          </select>
          <button
            type="button"
            aria-pressed={hideFailed}
            disabled={status === "failed"}
            onClick={() => setFilter({ hide_failed: !hideFailed })}
            className={toggleClass(hideFailed)}
          >
            <Icon name={hideFailed ? "check" : "filter"} size={14} />
            {t("history.hideFailed")}
          </button>
          {anyFilter && (
            <Button variant="ghost" size="sm" onClick={clearAll} className="ml-auto">
              <Icon name="close" size={14} />
              {t("history.clearFilters")}
            </Button>
          )}
        </div>
      </section>

      <ErrorText error={error} />
      {jobs.length === 0 ? (
        loading ? null : anyFilter ? (
          <EmptyState
            icon={<Icon name="search" size={22} />}
            title={t("history.noMatch")}
            hint={<Button variant="ghost" size="sm" onClick={clearAll}>{t("history.clearFilters")}</Button>}
          />
        ) : (
          <EmptyState icon={<Icon name="history" size={22} />} title={t("history.empty")} />
        )
      ) : (
        <div className="masonry columns-1 sm:columns-2 xl:columns-3" aria-busy={loading}>
          {jobs.map((j, i) => (
            <JobCard
              key={j.id}
              job={j}
              index={i % 12}
              onRemix={(job) => navigate("/", { state: { remix: job } })}
              onRetry={retry}
              onDelete={remove}
              onChange={(u) => setJobs((p) => p.map((x) => (x.id === u.id ? u : x)))}
              onAnimate={(asset) => navigate("/", { state: { animate: asset } })}
              onEdit={async (asset, instruction) => {
                await api(`/api/assets/${asset.id}/edit`, { method: "POST", body: { instruction } });
                navigate("/");
              }}
              onUpscale={async (asset, target) => {
                try {
                  await api(`/api/assets/${asset.id}/upscale`, { method: "POST", body: { target } });
                  navigate("/");
                } catch (err) {
                  setError(err);
                }
              }}
            />
          ))}
        </div>
      )}
      {more && (
        <div className="mt-6 text-center">
          <Button variant="ghost" disabled={loading} onClick={() => void load(jobs[jobs.length - 1]?.created_at).catch(setError)}>
            {t("history.loadMore")}
          </Button>
        </div>
      )}
    </div>
  );
}
