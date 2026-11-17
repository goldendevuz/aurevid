// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { ModelInfo, Provider } from "../types";
import { Icon } from "./icons";
import { Badge, Segmented } from "./ui";

export interface ModelChoice {
  p: Provider;
  m: ModelInfo;
}

/** Deterministic decorative gradient per model so cards are recognisable without any artwork. */
function swatch(seed: string): string {
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const a = h % 360;
  return `linear-gradient(135deg, hsl(${a} 80% 62%), hsl(${(a + 70) % 360} 75% 52%) 60%, hsl(${(a + 140) % 360} 70% 45%))`;
}

export function ModelSwatch({ seed, size = 36 }: { seed: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-block shrink-0 rounded-xl shadow-[inset_0_1px_0_rgb(255_255_255/0.35)]"
      style={{ width: size, height: size, background: swatch(seed) }}
    />
  );
}

export default function ModelPicker({
  choices,
  value,
  mode,
  onSelect,
  onClose,
}: {
  choices: ModelChoice[];
  value: string;
  mode: "image" | "video";
  onSelect: (key: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<"all" | "free" | "paid">("all");
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

  const shown = useMemo(
    () => choices.filter(({ p }) => filter === "all" || p.tier === filter),
    [choices, filter],
  );

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
            <h2 id="model-picker-title" className="text-lg font-semibold tracking-tight">
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
        <div className="grid gap-3 overflow-y-auto p-5 pt-2 sm:grid-cols-2">
          {shown.length === 0 && <p className="col-span-full py-8 text-center text-sm text-muted">{t("studio.noModelsInFilter")}</p>}
          {shown.map(({ p, m }) => {
            const key = `${p.id}|${m.id}`;
            const active = key === value;
            const locked = !p.available;
            return (
              <div key={key} className={`rounded-2xl border bg-raised/50 p-4 transition ${active ? "ring-aurora border-transparent" : "border-line hover:border-white/20"}`}>
                <button
                  type="button"
                  disabled={locked}
                  onClick={() => {
                    onSelect(key);
                    onClose();
                  }}
                  aria-pressed={active}
                  className="flex w-full items-start gap-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <ModelSwatch seed={key} size={40} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold">{m.label}</span>
                      {active && <Icon name="check" size={15} className="shrink-0 text-accent" />}
                    </span>
                    <span className="block text-[11px] text-muted">{p.name}</span>
                  </span>
                </button>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Badge tone={p.tier === "free" ? "free" : "paid"}>{p.tier === "free" ? t("studio.free") : t("studio.paid")}</Badge>
                  <Badge tone={m.commercial_use === "yes" ? "ok" : "muted"}>{t(`studio.commercial_${m.commercial_use}`)}</Badge>
                  {p.key_source === "user" && <Badge tone="muted">{t("studio.byok")}</Badge>}
                </div>
                <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
                  <li className="flex items-center gap-1"><Icon name="ratio" size={12} />{m.aspect_ratios.join(" · ")}</li>
                  {m.kind === "image" ? (
                    <li className="flex items-center gap-1"><Icon name="layers" size={12} />{t("studio.upToImages", { count: m.max_count })}</li>
                  ) : (
                    m.durations.length > 0 && (
                      <li className="flex items-center gap-1"><Icon name="clock" size={12} />{[...m.durations].sort((a, b) => a - b).map((d) => `${d}s`).join(" / ")}</li>
                    )
                  )}
                  {m.accepts_image && <li className="flex items-center gap-1"><Icon name="image" size={12} />{t("studio.acceptsImage")}</li>}
                  {m.upscale_targets.length > 0 && (
                    <li className="flex items-center gap-1"><Icon name="expand" size={12} />{m.upscale_targets.map((x) => x.toUpperCase()).join(" / ")}</li>
                  )}
                  <li className="flex items-center gap-1"><Icon name="bolt" size={12} />{t("studio.perImage", { count: m.credit_cost })}</li>
                </ul>
                {locked && (
                  <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
                    <span className="flex items-center gap-1 text-muted"><Icon name="lock" size={12} />{t("studio.needsKey")}</span>
                    <Link to="/settings" onClick={onClose} className="font-semibold text-accent hover:underline">{t("nav.settings")}</Link>
                    {p.key_url && (
                      <a href={p.key_url} target="_blank" rel="noopener noreferrer" className="text-accent-2 hover:underline">
                        {t("settings.getKey")} ↗
                      </a>
                    )}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
