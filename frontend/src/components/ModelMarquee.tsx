// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { ProviderDot } from "./ProviderDot";

/** One entry of the public `/api/catalog/models` (the same registry the Studio uses, no credentials). */
export interface PublicModel {
  provider_id: string;
  provider: string;
  id: string;
  label: string;
  kind: "image" | "video";
}

const MIN_ITEMS_PER_COPY = 12; // enough chips to cover a wide screen before the loop restarts
const SECONDS_PER_CHIP = 5;

/**
 * Slow endless strip of the models Aurevid really offers. The list is fetched from the backend registry, never
 * hard-coded; if the request fails or returns nothing the strip is simply not rendered.
 */
export default function ModelMarquee() {
  const { t } = useTranslation();
  const [models, setModels] = useState<PublicModel[]>([]);

  useEffect(() => {
    let alive = true;
    api<PublicModel[]>("/api/catalog/models")
      .then((m) => alive && setModels(m))
      .catch(() => alive && setModels([]));
    return () => {
      alive = false;
    };
  }, []);

  if (models.length === 0) return null;

  // Repeat the real list inside one copy when it is short; repeats are hidden from assistive tech and from the static layout.
  const reps = Math.max(1, Math.ceil(MIN_ITEMS_PER_COPY / models.length));
  const items = Array.from({ length: reps }, (_, r) => models.map((m) => ({ m, rep: r > 0 }))).flat();
  const copy = (hidden: boolean) =>
    items.map(({ m, rep }, i) => (
      <li
        key={`${m.provider_id}|${m.id}|${i}`}
        aria-hidden={hidden || rep ? true : undefined}
        title={m.provider}
        className={`flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5 font-mono text-xs text-ink/90 ${
          hidden || rep ? "marquee-dup" : ""
        }`}
      >
        <ProviderDot id={m.provider_id} />
        {m.label}
      </li>
    ));

  return (
    <section aria-label={t("landing.marquee.label")} className="mx-auto max-w-7xl px-4 pb-4 pt-6 sm:px-6">
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-accent-4/30 bg-accent-4/10 px-2.5 py-0.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-accent-4">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-4" aria-hidden />
          {t("landing.livePreview")}
        </span>
        <p className="text-sm font-semibold text-ink">{t("landing.marquee.title")}</p>
        <span className="font-mono text-xs text-muted">
          <span className="text-accent-4">{t("landing.marquee.count", { count: models.length })}</span>
        </span>
      </div>
      <div className="marquee" style={{ ["--marquee-s" as string]: `${items.length * SECONDS_PER_CHIP}s` }}>
        <div className="marquee-track">
          <ul className="marquee-copy">{copy(false)}</ul>
          <ul className="marquee-copy marquee-dup" aria-hidden>
            {copy(true)}
          </ul>
        </div>
      </div>
    </section>
  );
}
