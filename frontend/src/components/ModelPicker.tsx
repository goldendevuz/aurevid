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
  const [inactiveToggled, setInactiveToggled] = useState<boolean | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab" || !dialogRef.current) return;
      // Minimal focus trap.
      const nodes = dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])");
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

  const shown = useMemo(
    () => activeChoices.filter(({ p }) => filter === "all" || p.tier === filter),
    [activeChoices, filter],
  );

  const inactiveShown = useMemo(
    () => inactive.filter((m) => m.kind === mode),
    [inactive, mode],
  );

  const inactiveOpen = shouldExpandInactive(shown.length, inactiveToggled);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
      <button type="button" aria-label={t("studio.close")} tabIndex={-1} onClick={onClose} className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-picker-title"
        tabIndex={-1}
        className="glass rise relative flex max-h-[88vh] w-full max-w-3xl flex-col rounded-t-3xl bg-surface outline-none sm:rounded-3xl"
      >
        <div className="flex items-start justify-between gap-4 p-5 pb-3">
          <div>
            <h2 id="model-picker-title" className="text-xl tracking-[0.02em]">
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
            <Icon name="close" />
          </button>
        </div>
        <div className="px-5 pb-3">
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
        <div className="overflow-y-auto p-5 pt-2">
          {shown.length === 0 && (
            <p className="py-4 text-center text-sm text-muted">{t("studio.noModelsInFilter")}</p>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            {shown.map(({ p, m }) => {
              const key = `${p.id}|${m.id}`;
              const active = key === value;
              return (
                <div key={key} className={`rounded-2xl border bg-raised/50 p-4 transition ${active ? "ring-aurora border-transparent" : "border-line hover:border-white/20"}`}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(key);
                      onClose();
                    }}
                    aria-pressed={active}
                    className="flex w-full items-start gap-3 text-left"
                  >
                    <ModelSwatch seed={key} size={40} provider={p.id} />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="truncate text-sm font-semibold">{m.label}</span>
                        {active && <Icon name="check" size={15} className="shrink-0 text-accent" />}
                      </span>
                      <span className="flex items-center gap-1.5 text-[11px] text-muted">
                        {p.name}
                        {p.available && (
                          <span className="inline-flex items-center" title={t("studio.panel.ready")}>
                            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent-4 shadow-[0_0_6px_rgb(200_255_46/0.7)]" />
                            <span className="sr-only">{t("studio.panel.ready")}</span>
                          </span>
                        )}
                      </span>
                    </span>
                  </button>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Badge tone={p.tier === "free" ? "free" : "paid"}>{p.tier === "free" ? t("studio.free") : t("studio.paid")}</Badge>
                    <Badge tone={m.commercial_use === "yes" ? "ok" : "muted"}>{t(`studio.commercial_${m.commercial_use}`)}</Badge>
                    {p.key_source === "user" && <Badge tone="muted">{t("studio.byok")}</Badge>}
                    {p.key_source === "server" && p.free_left !== null && <Badge tone="free">{t("studio.freeLeft", { count: p.free_left })}</Badge>}
                  </div>
                  <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-muted">
                    <li className="flex items-center gap-1"><Icon name="ratio" size={12} />{m.aspect_ratios.join(" · ")}</li>
                    {m.kind === "image" ? (
                      <li className="flex items-center gap-1"><Icon name="layers" size={12} />{t("studio.upToImages", { count: m.max_count })}</li>
                    ) : (
                      m.durations.length > 0 && (
                        <li className="flex items-center gap-1"><Icon name="clock" size={12} />{[...m.durations].sort((a, b) => a - b).map((d) => `${d}s`).join(" / ")}</li>
                      )
                    )}
                    {m.has_audio && <li className="flex items-center gap-1 font-medium text-accent"><Icon name="sound" size={12} />{t("studio.withAudio")}</li>}
                    {m.accepts_image && <li className="flex items-center gap-1"><Icon name="image" size={12} />{t("studio.acceptsImage")}</li>}
                    {m.upscale_targets.length > 0 && (
                      <li className="flex items-center gap-1"><Icon name="expand" size={12} />{m.upscale_targets.map((x) => x.toUpperCase()).join(" / ")}</li>
                    )}
                    <li className="flex items-center gap-1"><Icon name="bolt" size={12} />{t("studio.perImage", { count: m.credit_cost })}</li>
                  </ul>
                  <p className="mt-2 font-mono text-[11px] font-medium text-ink/90">
                    {(() => {
                      const target = upscale && m.upscale_targets.includes(upscale as "4k" | "8k") ? upscale : null;
                      const price = priceOf(m, m.kind === "video" ? 1 : Math.min(count, m.max_count), target);
                      return price.count > 1
                        ? t("price.selectionMany", { count: price.total, n: price.count, each: price.each })
                        : t("price.selection", { count: price.total });
                    })()}
                    {onFreeShare(p) && <span className="ml-1 font-normal text-ok">· {t("price.freeShare")}</span>}
                  </p>
                </div>
              );
            })}
          </div>

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
                    {t("studio.inactiveTitle")}
                  </span>
                  <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-muted font-mono">
                    {inactiveShown.length}
                  </span>
                </div>
                <span className="text-xs text-muted hover:text-ink">
                  {inactiveOpen ? t("studio.collapseSection") : t("studio.expandSection")}
                </span>
              </button>

              {inactiveOpen && (
                <div className="mt-3 space-y-2">
                  {inactiveShown.map((m) => (
                    <div
                      key={`${m.provider_id}|${m.id}`}
                      className="flex items-center justify-between gap-3 rounded-2xl border border-line/50 bg-raised/20 p-3 opacity-60 transition cursor-not-allowed select-none"
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
                          {t("studio.connectKey")}
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
