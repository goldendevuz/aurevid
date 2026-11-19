// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Footer, LanguageSelect, Logo } from "../components/Layout";
import { Icon, type IconName } from "../components/icons";

/** Real interactive sample tiles rendered in the hero */
const HERO_TILES = [
  {
    key: "t1",
    type: "video",
    src: "/samples/gta6_cinematic.mp4",
    poster: "/samples/gta6_vice_city.jpg",
    ratio: "16 / 10",
    tilt: -2,
    badge: "GTA VI Trend",
  },
  {
    key: "t2",
    type: "video",
    src: "/samples/golden_leaf.mp4",
    ratio: "16 / 9",
    tilt: 2,
    badge: "Wan 2.2 Modal",
  },
  {
    key: "t3",
    type: "video",
    src: "/samples/cyber_synth.mp4",
    ratio: "16 / 9",
    tilt: -1.5,
    badge: "Cyberpunk 4K",
  },
  {
    key: "t4",
    type: "video",
    src: "/samples/aurora_drift.mp4",
    ratio: "16 / 10",
    tilt: 2.5,
    badge: "Aurora Motion",
  },
] as const;

interface ShowcaseItem {
  id: string;
  kind: "video" | "image";
  src: string;
  poster?: string;
  titleKey: string;
  descKey: string;
  badge: string;
  model: string;
  aspect: string;
  prompt: string;
}

const SHOWCASE_ITEMS: ShowcaseItem[] = [
  {
    id: "gta6_video",
    kind: "video",
    src: "/samples/gta6_cinematic.mp4",
    poster: "/samples/gta6_vice_city.jpg",
    titleKey: "sample_gta6_title",
    descKey: "sample_gta6_desc",
    badge: "GTA VI • Video",
    model: "Aurevid Cinema / Wan 2.2",
    aspect: "16:9",
    prompt:
      "Grand Theft Auto VI Vice City tropical aesthetic, protagonist in floral Hawaiian shirt, sunglasses, neon Miami sunset, billboard, helicopter in sky, luxury sports car, cinematic 4K photorealism",
  },
  {
    id: "golden_leaf",
    kind: "video",
    src: "/samples/golden_leaf.mp4",
    titleKey: "sample_golden_leaf_title",
    descKey: "sample_golden_leaf_desc",
    badge: "Wan 2.2 • Modal GPU",
    model: "Wan 2.2 TI2V-5B (BYOK Modal)",
    aspect: "16:9",
    prompt:
      "A single golden leaf falls slowly through soft morning light, spinning gently as it descends against a blurred forest background, high cinematic motion, 24fps",
  },
  {
    id: "gta6_poster",
    kind: "image",
    src: "/samples/gta6_vice_city.jpg",
    titleKey: "sample_gta6_art_title",
    descKey: "sample_gta6_art_desc",
    badge: "GTA VI • Art",
    model: "FLUX Ultra Photoreal",
    aspect: "16:9",
    prompt:
      "Grand Theft Auto VI x Updaily, Vice City neon nightlife, bold typography, retro palms, cinematic action art poster, sunset lighting",
  },
  {
    id: "cyber_synth",
    kind: "video",
    src: "/samples/cyber_synth.mp4",
    titleKey: "sample_cyber_title",
    descKey: "sample_cyber_desc",
    badge: "Synthwave • 60 FPS",
    model: "Aurevid Motion",
    aspect: "16:9",
    prompt:
      "80s synthwave neon highway at sunset, digital wireframe horizon grid, vibrant magenta and cyan glow, retrofuturism aesthetic, endless drive",
  },
  {
    id: "aurora_flow",
    kind: "video",
    src: "/samples/aurora_drift.mp4",
    titleKey: "sample_aurora_title",
    descKey: "sample_aurora_desc",
    badge: "Aurora • Motion",
    model: "Cosmic Flow Video",
    aspect: "16:9",
    prompt:
      "Atmospheric aurora borealis ribbons dancing across Arctic night sky, cosmic glow, hyper-detail, slow fluid particle movement",
  },
];

const FEATURES: { key: string; icon: IconName }[] = [
  { key: "models", icon: "layers" },
  { key: "video", icon: "video" },
  { key: "upscale", icon: "expand" },
  { key: "remix", icon: "sparkle" },
  { key: "keys", icon: "key" },
  { key: "open", icon: "shield" },
];

const STEPS = ["s1", "s2", "s3"] as const;

export default function Landing() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<"all" | "video" | "image">("all");

  const filteredItems = SHOWCASE_ITEMS.filter((item) => {
    if (filter === "all") return true;
    return item.kind === filter;
  });

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 bg-gradient-to-b from-bg via-bg/80 to-transparent backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
          <Logo />
          <nav aria-label="Main" className="glass ml-4 hidden gap-0.5 rounded-full p-1 md:flex">
            {(["showcase", "features", "how"] as const).map((id) => (
              <a
                key={id}
                href={`#${id}`}
                className="rounded-full px-3.5 py-1.5 text-sm font-medium text-muted transition hover:bg-white/[0.06] hover:text-ink"
              >
                {t(`landing.nav_${id}`)}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LanguageSelect />
            <Link
              to="/login"
              className="rounded-full px-3.5 py-2 text-sm font-medium text-ink transition hover:bg-white/[0.06]"
            >
              {t("nav.login")}
            </Link>
            <Link
              to="/register"
              className="btn-aurora hidden rounded-full px-4 py-2 text-sm font-semibold sm:inline-flex"
            >
              {t("landing.start")}
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* HERO SECTION */}
        <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-16 pt-10 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:pt-20">
          <div>
            <p className="rise mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3.5 py-1 text-[11px] font-medium text-muted backdrop-blur">
              <span className="h-2 w-2 animate-ping rounded-full bg-accent" />
              <Icon name="sparkle" size={13} className="text-accent" />
              {t("auth.heroEyebrow")}
            </p>
            <h1 className="rise text-5xl font-bold leading-[1] tracking-[-0.04em] [--i:1] sm:text-7xl">
              <span className="block">{t("auth.heroLead")}</span>
              <span className="aurora-text block pb-1">{t("auth.heroAccent")}</span>
            </h1>
            <p className="rise mt-6 max-w-xl text-base text-muted [--i:2] sm:text-lg">
              {t("auth.heroSub")}
            </p>
            <div className="rise mt-8 flex flex-wrap items-center gap-3 [--i:3]">
              <Link
                to="/register"
                className="btn-aurora inline-flex items-center gap-2 rounded-2xl px-6 py-3.5 text-base font-semibold shadow-lg shadow-accent/20"
              >
                <Icon name="sparkle" size={18} />
                {t("landing.start")}
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/[0.04] px-6 py-3.5 text-base font-medium text-ink transition hover:border-white/30 hover:bg-white/[0.08]"
              >
                {t("nav.login")}
              </Link>
              <a
                href="#showcase"
                className="inline-flex items-center gap-2 rounded-2xl border border-line bg-white/[0.02] px-4 py-3.5 text-sm font-medium text-muted transition hover:border-white/20 hover:text-ink"
              >
                <Icon name="video" size={16} />
                {t("landing.nav_showcase")} ↓
              </a>
            </div>
            <ul className="rise mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted [--i:4]">
              {(["free", "keys", "open"] as const).map((k) => (
                <li key={k} className="flex items-center gap-1.5">
                  <Icon name="check" size={14} className="text-accent" />
                  {t(`landing.trust_${k}`)}
                </li>
              ))}
            </ul>
          </div>

          {/* HERO TILES (Auto-playing real video previews) */}
          <div className="relative mx-auto grid w-full max-w-xl grid-cols-2 items-center gap-4" aria-label="Sample generations">
            {HERO_TILES.map((x, i) => (
              <figure
                key={x.key}
                className={`tile rise spot group relative overflow-hidden rounded-[22px] border border-white/15 bg-raised/50 shadow-2xl transition duration-500 hover:scale-[1.03] hover:border-accent/50 ${
                  i % 2 ? "translate-y-6" : ""
                }`}
                style={{
                  aspectRatio: x.ratio,
                  transform: `rotate(${x.tilt}deg)`,
                  ["--i" as string]: i + 2,
                }}
              >
                <video
                  src={x.src}
                  poster={"poster" in x ? x.poster : undefined}
                  autoPlay
                  loop
                  muted
                  playsInline
                  preload="auto"
                  className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
                />
                <span className="absolute left-2.5 top-2.5 flex items-center gap-1 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-bold tracking-wide text-ink backdrop-blur border border-white/10">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ok" />
                  {x.badge}
                </span>
                <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-3 pt-8 text-[11px] leading-snug text-ink/90 opacity-90 transition duration-300 group-hover:opacity-100">
                  {t(`landing.${x.key}`)}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>

        {/* TRENDING SHOWCASE SECTION (GTA VI & Live creations) */}
        <section id="showcase" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
                <span className="h-2 w-2 rounded-full bg-accent animate-ping" />
                {t("landing.livePreview")}
              </div>
              <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-5xl">
                {t("landing.showcaseTitle")}
              </h2>
              <p className="mt-2 max-w-2xl text-sm text-muted sm:text-base">
                {t("landing.showcaseSub")}
              </p>
            </div>

            {/* Filter buttons */}
            <div className="flex rounded-xl border border-line bg-raised/60 p-1 backdrop-blur self-start sm:self-auto">
              {(["all", "video", "image"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
                    filter === f ? "bg-white/10 text-ink shadow-sm" : "text-muted hover:text-ink"
                  }`}
                >
                  {t(`landing.filter_${f}`)}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {filteredItems.map((item) => (
              <article
                key={item.id}
                className="group glass spot overflow-hidden rounded-[24px] border border-white/10 bg-raised/30 transition duration-500 hover:border-white/25 hover:shadow-2xl"
              >
                <div className="relative overflow-hidden aspect-video bg-black/60">
                  {item.kind === "video" ? (
                    <video
                      src={item.src}
                      poster={item.poster}
                      autoPlay
                      loop
                      muted
                      playsInline
                      preload="auto"
                      className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
                    />
                  ) : (
                    <img
                      src={item.src}
                      alt={t(`landing.${item.titleKey}`)}
                      loading="lazy"
                      className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
                    />
                  )}

                  {/* Top Badges */}
                  <div className="absolute left-3 top-3 flex items-center gap-1.5">
                    <span className="flex items-center gap-1 rounded-full bg-black/70 px-2.5 py-1 text-[10px] font-semibold text-ink backdrop-blur border border-white/10">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                      {item.badge}
                    </span>
                  </div>

                  <span className="absolute right-3 top-3 rounded-full bg-black/70 px-2.5 py-1 text-[10px] font-mono text-muted backdrop-blur border border-white/10">
                    {item.aspect}
                  </span>
                </div>

                <div className="p-5">
                  <div className="flex items-center justify-between gap-2 text-xs text-muted">
                    <span className="flex items-center gap-1 font-medium text-ink/80">
                      <Icon name={item.kind === "video" ? "video" : "image"} size={13} />
                      {item.model}
                    </span>
                  </div>

                  <h3 className="mt-2 text-base font-bold text-ink">
                    {t(`landing.${item.titleKey}`)}
                  </h3>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">
                    {t(`landing.${item.descKey}`)}
                  </p>

                  <div className="mt-4 flex items-center justify-between gap-3 border-t border-line/60 pt-4">
                    <span className="text-[11px] font-mono text-muted/70">
                      Prompt ready
                    </span>
                    <Link
                      to="/register"
                      state={{ prefill: { prompt: item.prompt, aspect: item.aspect } }}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/[0.06] px-3 py-1.5 text-xs font-semibold text-ink transition hover:border-accent hover:bg-accent/15 hover:text-accent"
                    >
                      <Icon name="sparkle" size={13} />
                      {t("landing.tryPrompt")}
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* FEATURES SECTION */}
        <section id="features" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6">
          <h2 className="max-w-2xl text-3xl font-bold tracking-tight sm:text-5xl">
            {t("landing.featuresTitle")}
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <article
                key={f.key}
                className="glass spot rise rounded-[var(--radius-card)] p-6"
                style={{ ["--i" as string]: i }}
              >
                <span className="mb-4 grid h-11 w-11 place-items-center rounded-2xl border border-white/10 bg-white/[0.04] text-accent">
                  <Icon name={f.icon} size={20} />
                </span>
                <h3 className="font-display text-lg font-bold tracking-tight">
                  {t(`landing.f_${f.key}`)}
                </h3>
                <p className="mt-1.5 text-sm text-muted">{t(`landing.f_${f.key}_desc`)}</p>
              </article>
            ))}
          </div>
        </section>

        {/* HOW IT WORKS SECTION */}
        <section id="how" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6">
          <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
            {t("landing.howTitle")}
          </h2>
          <ol className="mt-10 grid gap-4 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s} className="glass rounded-[var(--radius-card)] p-6">
                <span className="aurora-text font-display text-5xl font-bold">{i + 1}</span>
                <h3 className="mt-3 font-display text-lg font-bold">{t(`landing.${s}`)}</h3>
                <p className="mt-1.5 text-sm text-muted">{t(`landing.${s}_desc`)}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* CALL TO ACTION */}
        <section className="mx-auto max-w-7xl px-4 pb-20 pt-8 sm:px-6">
          <div className="glass ring-aurora spot rounded-[32px] px-6 py-14 text-center sm:px-12">
            <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight sm:text-5xl">
              {t("landing.ctaTitle")}
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-muted">{t("auth.bonus")}</p>
            <Link
              to="/register"
              className="btn-aurora mt-8 inline-flex items-center gap-2 rounded-2xl px-7 py-3.5 text-base font-semibold shadow-xl shadow-accent/20"
            >
              <Icon name="sparkle" size={18} />
              {t("landing.start")}
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
