// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { onFreeShare, priceOf } from "../pricing";
import type { InactiveModel, ModelInfo, Provider } from "../types";
import { Icon } from "./icons";
import { ProviderDot } from "./ProviderDot";
import { Badge, Segmented } from "./ui";

export interface ModelChoice {
  p: Provider;
  m: ModelInfo;
}

export function shouldExpandInactive(activeCount: number, userToggled?: boolean | null): boolean {
  if (userToggled !== null && userToggled !== undefined) {
    return userToggled;
  }
  return activeCount === 0;
}

export function formatInactiveModelLink(m: InactiveModel): { path: string; labelKey: string } {
  return {
    path: m.settings_path || "/settings",
    labelKey: "studio.connectKey",
  };
}

export function getModelFamily(m: ModelInfo): string {
  const label = m.label.trim();
  const id = m.id.toLowerCase();
  if (/^Seedance/i.test(label) || id.includes("seedance")) return "Seedance";
  if (/^FLUX/i.test(label) || id.includes("flux")) return "FLUX";
  if (/^Wan/i.test(label) || id.includes("wan")) return "Wan";
  if (/^Kling/i.test(label) || id.includes("kling")) return "Kling";
  if (/^(Minimax|Hailuo)/i.test(label) || id.includes("hailuo") || id.includes("minimax")) return "Minimax Hailuo";
  if (/^(Google|Veo)/i.test(label) || id.includes("veo")) return "Google Veo";
  if (/^Gemini/i.test(label) || id.includes("gemini")) return "Gemini";
  if (/^Grok/i.test(label) || id.includes("grok")) return "Grok Imagine";
  if (/^(DALL|GPT|OpenAI)/i.test(label) || id.includes("gpt") || id.includes("dall")) return "OpenAI";
  if (/^Midjourney/i.test(label)) return "Midjourney";
  return label.split(/[\s._-]/)[0] || "Other";
}

/** Deterministic decorative gradient per model so cards are recognisable without any artwork. */
function swatch(seed: string): string {
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const a = h % 360;
  return `linear-gradient(135deg, hsl(${a} 80% 62%), hsl(${(a + 70) % 360} 75% 52%) 60%, hsl(${(a + 140) % 360} 70% 45%))`;
}

/** `provider` adds a small provider-coloured dot on the corner (same colour as in the landing marquee). */
export function ModelSwatch({ seed, size = 36, provider }: { seed: string; size?: number; provider?: string }) {
  return (
    <span aria-hidden className="relative inline-block shrink-0" style={{ width: size, height: size }}>
      <span
        className="block h-full w-full rounded-xl shadow-[inset_0_1px_0_rgb(255_255_255/0.35)]"
        style={{ background: swatch(seed) }}
      />
      {provider && <ProviderDot id={provider} size={Math.max(7, Math.round(size / 3.4))} className="absolute -bottom-0.5 -right-0.5 ring-2 ring-surface" />}
    </span>
  );
}

export default function ModelPicker({
  choices,
  inactive = [],
  value,
  mode,
  onSelect,
  onClose,
  count = 1,
  upscale = null,
}: {
  choices: ModelChoice[];
  inactive?: InactiveModel[];
  value: string;
  mode: "image" | "video";
  count?: number; // outputs in the current selection, for the upfront price
  upscale?: string | null;
  onSelect: (key: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<"all" | "free" | "paid">("all");
  const [query, setQuery] = useState("");
  const [inactiveToggled, setInactiveToggled] = useState<boolean | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    searchInputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab" || !dialogRef.current) return;
      // Minimal focus trap.
      const nodes = dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex='-1'])");
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [onClose]);

  // Active choices only include models the user can run right now
  const activeChoices = useMemo(
    () => choices.filter(({ p, m }) => p.available && (m.commercial_use === "yes" || p.key_source === "user")),
    [choices],
  );

  const q = query.trim().toLowerCase();

  const shown = useMemo(() => {
    return activeChoices.filter(({ p, m }) => {
      if (filter !== "all" && p.tier !== filter) return false;
      if (!q) return true;
      const family = getModelFamily(m).toLowerCase();
      return (
        m.label.toLowerCase().includes(q) ||
        m.id.toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        family.includes(q)
      );
    });
  }, [activeChoices, filter, q]);

  // Featured models: top models matching kind
  const featured = useMemo(() => {
    if (q) return []; // Hide featured section during search to keep results focused
    return activeChoices
      .filter(({ m }) => m.publish_quality || /seedance|flux|wan|kling/i.test(m.label))
      .slice(0, 3);
  }, [activeChoices, q]);

  // Group shown models by family
  const families = useMemo(() => {
    const map = new Map<string, ModelChoice[]>();
    for (const item of shown) {
      const fam = getModelFamily(item.m);
      const list = map.get(fam) || [];
      list.push(item);
      map.set(fam, list);
    }
    return Array.from(map.entries());
  }, [shown]);

  const inactiveShown = useMemo(() => {
    return inactive.filter((m) => {
      if (m.kind !== mode) return false;
      if (!q) return true;
      return (
        m.label.toLowerCase().includes(q) ||
        m.id.toLowerCase().includes(q) ||
        m.provider_name.toLowerCase().includes(q) ||
        m.reason.toLowerCase().includes(q)
      );
    });
  }, [inactive, mode, q]);

  const inactiveOpen = shouldExpandInactive(shown.length, inactiveToggled);

  const computePrice = (item: ModelChoice) => {
    const { p, m } = item;
    const target = upscale && m.upscale_targets.includes(upscale as "4k" | "8k") ? upscale : null;
    const price = priceOf(m, m.kind === "video" ? 1 : Math.min(count, m.max_count), target);
    return {
      text: price.count > 1
        ? t("price.selectionMany", { count: price.total, n: price.count, each: price.each })
        : t("price.selection", { count: price.total }),
      freeShare: onFreeShare(p),
    };
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
      <button type="button" aria-label={t("studio.close")} tabIndex={-1} onClick={onClose} className="absolute inset-0 bg-black/80 backdrop-blur-md" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-picker-title"
        tabIndex={-1}
        className="glass rise relative flex max-h-[90vh] w-full max-w-4xl flex-col rounded-t-[24px] bg-surface-1 outline-none sm:rounded-[24px]"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-5 pb-3">
          <div>
            <h2 id="model-picker-title" className="text-xl font-semibold tracking-[-0.02em]">
              {mode === "video" ? t("studio.pickVideoModel") : t("studio.pickModel")}
            </h2>
            <p className="mt-0.5 text-xs text-muted">{t("studio.pickModelHint")}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("studio.close")}
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-muted transition hover:bg-white/[0.06] hover:text-ink"
          >
            <Icon name="close" size={18} />
          </button>
        </div>

        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 px-5 pb-3">
          <div className="relative flex-1">
            <Icon name="search" size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("studio.searchModels") || "Search models, providers, features..."}
              className="w-full rounded-xl border border-line bg-surface-2 pl-9 pr-8 py-2 text-xs text-ink placeholder:text-muted/60 focus:border-accent/60 focus:outline-none"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-ink"
                aria-label="Clear search"
              >
                <Icon name="close" size={14} />
              </button>
            )}
          </div>
          <Segmented
            label={t("studio.pickModel")}
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: t("studio.filterAll") },
              { value: "free", label: t("studio.free") },
              { value: "paid", label: t("studio.paid") },
            ]}
          />
        </div>

        {/* Scrollable Model List */}
        <div className="overflow-y-auto px-5 pb-6 pt-1 space-y-6">
          {/* Featured Models Row (when not searching) */}
          {featured.length > 0 && (
            <div>
              <p className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
                <Icon name="sparkle" size={13} className="text-accent" />
                {t("studio.featuredModels") || "Featured models"}
              </p>
              <div className="grid gap-3 sm:grid-cols-3">
                {featured.map(({ p, m }) => {
                  const key = `${p.id}|${m.id}`;
                  const active = key === value;
                  const price = computePrice({ p, m });
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => {
                        onSelect(key);
                        onClose();
                      }}
                      className={`group relative flex flex-col justify-between overflow-hidden rounded-2xl border p-3.5 text-left transition ${
                        active
                          ? "border-accent bg-accent/[0.06] shadow-[0_0_15px_rgba(200,255,46,0.1)]"
                          : "border-line bg-surface-2 hover:border-white/20 hover:bg-surface-3"
                      }`}
                    >
                      <div className="mb-3 flex items-start justify-between gap-2">
                        <ModelSwatch seed={key} size={38} provider={p.id} />
                        {active ? (
                          <span className="grid h-5 w-5 place-items-center rounded-full bg-accent text-black">
                            <Icon name="check" size={12} strokeWidth={3} />
                          </span>
                        ) : (
                          <Badge tone="live">TOP</Badge>
                        )}
                      </div>
                      <div>
                        <p className="truncate text-sm font-semibold text-ink group-hover:text-accent transition">
                          {m.label}
                        </p>
                        <p className="mt-0.5 line-clamp-1 text-[11px] text-muted">
                          {p.name} · {m.commercial_use === "yes" ? "Commercial OK" : "Personal"}
                        </p>
                      </div>
                      <div className="mt-3 flex items-center justify-between border-t border-line/60 pt-2 text-[11px]">
                        <span className="font-mono text-ink/90">{price.text}</span>
                        {price.freeShare && <span className="text-ok">Free</span>}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Empty search results */}
          {shown.length === 0 && (
            <div className="py-8 text-center">
              <p className="text-sm text-muted">
                {query ? `No models found matching "${query}"` : t("studio.noModelsInFilter")}
              </p>
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="mt-2 text-xs text-accent hover:underline"
                >
                  Clear search
                </button>
              )}
            </div>
          )}

          {/* Grouped by Family */}
          {families.map(([family, members]) => (
            <div key={family}>
              <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-muted">
                {family}
              </p>
              <div className="space-y-2">
                {members.map(({ p, m }) => {
                  const key = `${p.id}|${m.id}`;
                  const active = key === value;
                  const price = computePrice({ p, m });
                  const durationsText = m.durations?.length
                    ? `${Math.min(...m.durations)}s–${Math.max(...m.durations)}s`
                    : null;
                  const maxRes = m.resolutions?.length
                    ? m.resolutions[m.resolutions.length - 1]
                    : m.upscale_targets?.length
                    ? m.upscale_targets[m.upscale_targets.length - 1].toUpperCase()
                    : null;

                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => {
                        onSelect(key);
                        onClose();
                      }}
                      className={`group flex w-full items-center justify-between gap-3 rounded-2xl border p-3 text-left transition ${
                        active
                          ? "border-accent bg-accent/[0.06] shadow-[0_0_12px_rgba(200,255,46,0.08)]"
                          : "border-line bg-surface-2 hover:border-white/20 hover:bg-surface-3"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <ModelSwatch seed={key} size={36} provider={p.id} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-semibold text-ink group-hover:text-accent transition">
                              {m.label}
                            </span>
                            <Badge tone={p.tier === "free" ? "free" : "paid"}>
                              {p.tier === "free" ? t("studio.free") : t("studio.paid")}
                            </Badge>
                            {m.commercial_use === "byok_only" && <Badge tone="muted">BYOK</Badge>}
                          </div>
                          {/* Spec chips */}
                          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[10px] text-muted">
                            <span className="text-muted/80">{p.name}</span>
                            {durationsText && (
                              <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono">
                                ⏱ {durationsText}
                              </span>
                            )}
                            {maxRes && (
                              <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono">
                                ◇ {maxRes}
                              </span>
                            )}
                            {m.has_audio && (
                              <span className="rounded bg-accent/10 px-1.5 py-0.5 text-accent font-medium">
                                ♪ Audio
                              </span>
                            )}
                            {m.accepts_image && (
                              <span className="rounded bg-surface-3 px-1.5 py-0.5">
                                Img
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-right">
                          <p className="font-mono text-xs font-semibold text-ink/90">{price.text}</p>
                          {price.freeShare && <p className="text-[10px] text-ok">· {t("price.freeShare")}</p>}
                        </div>
                        {active ? (
                          <span className="grid h-6 w-6 place-items-center rounded-full bg-accent text-black">
                            <Icon name="check" size={14} strokeWidth={3} />
                          </span>
                        ) : (
                          <span className="h-6 w-6 rounded-full border border-line group-hover:border-white/30" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Inactive models section below active models */}
          {inactiveShown.length > 0 && (
            <div className="mt-6 border-t border-line/60 pt-4">
              <button
                type="button"
                onClick={() => setInactiveToggled(!inactiveOpen)}
                aria-expanded={inactiveOpen}
                className="flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-left transition hover:bg-white/[0.04]"
              >
                <div className="flex items-center gap-2">
                  <Icon name="chevron" size={14} className={`text-muted transition-transform ${inactiveOpen ? "rotate-0" : "-rotate-90"}`} />
                  <span className="text-xs font-semibold text-muted">
                    {t("studio.inactiveTitle") || "Inactive — connect your key"}
                  </span>
                  <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-muted font-mono">
                    {inactiveShown.length}
                  </span>
                </div>
                <span className="text-xs text-muted hover:text-ink">
                  {inactiveOpen ? (t("studio.collapseSection") || "Collapse") : (t("studio.expandSection") || "Expand")}
                </span>
              </button>

              {inactiveOpen && (
                <div className="mt-3 space-y-2">
                  {inactiveShown.map((m) => (
                    <div
                      key={`${m.provider_id}|${m.id}`}
                      className="flex items-center justify-between gap-3 rounded-2xl border border-line/50 bg-surface-2/40 p-3 opacity-60 transition cursor-not-allowed select-none"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <ModelSwatch seed={`${m.provider_id}|${m.id}`} size={36} provider={m.provider_id} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-semibold text-muted">{m.label}</span>
                            <Badge tone="muted">{t(`studio.commercial_${m.commercial_use}`)}</Badge>
                          </div>
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted">
                            <span>{m.reason}</span>
                            <span>·</span>
                            <span className="font-mono text-ink/80">{m.price_text}</span>
                          </div>
                        </div>
                      </div>
                      <div className="shrink-0">
                        <Link
                          to={m.settings_path || "/settings"}
                          onClick={onClose}
                          className="inline-flex items-center gap-1 rounded-xl border border-line bg-surface px-3 py-1 text-xs font-semibold text-accent hover:underline hover:bg-white/[0.06]"
                        >
                          {t("studio.connectKey") || "Connect key"}
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
