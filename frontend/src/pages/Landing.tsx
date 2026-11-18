// SPDX-License-Identifier: AGPL-3.0-or-later
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Footer, LanguageSelect, Logo } from "../components/Layout";
import { Icon, type IconName } from "../components/icons";

/** Decorative sample tiles (CSS art, not real generations): a prompt on top of a moving colour field. */
const TILES = [
  { key: "t1", ratio: "4 / 5", a: "#ff6a3d", b: "#ffd23a", c: "#d4ff3a", tilt: -3 },
  { key: "t2", ratio: "1 / 1", a: "#2b5cff", b: "#8a5cff", c: "#ff5ca8", tilt: 2 },
  { key: "t3", ratio: "16 / 10", a: "#0fd9a0", b: "#0a6cff", c: "#12162a", tilt: -1.5 },
  { key: "t4", ratio: "4 / 5", a: "#ffcf9e", b: "#ff7a59", c: "#3a1b3f", tilt: 3 },
] as const;

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
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 bg-gradient-to-b from-bg via-bg/80 to-transparent">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
          <Logo />
          <nav aria-label="Main" className="glass ml-4 hidden gap-0.5 rounded-full p-1 md:flex">
            {(["features", "how"] as const).map((id) => (
              <a key={id} href={`#${id}`} className="rounded-full px-3.5 py-1.5 text-sm font-medium text-muted transition hover:bg-white/[0.06] hover:text-ink">
                {t(`landing.nav_${id}`)}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <LanguageSelect />
            <Link to="/login" className="rounded-full px-3.5 py-2 text-sm font-medium text-ink transition hover:bg-white/[0.06]">
              {t("nav.login")}
            </Link>
            <Link to="/register" className="btn-aurora hidden rounded-full px-4 py-2 text-sm font-semibold sm:inline-flex">
              {t("landing.start")}
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-16 pt-10 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:pt-20">
          <div>
            <p className="rise mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-medium text-muted backdrop-blur">
              <Icon name="sparkle" size={13} className="text-accent" />
              {t("auth.heroEyebrow")}
            </p>
            <h1 className="rise text-5xl font-bold leading-[1] tracking-[-0.04em] [--i:1] sm:text-7xl">
              <span className="block">{t("auth.heroLead")}</span>
              <span className="aurora-text block pb-1">{t("auth.heroAccent")}</span>
            </h1>
            <p className="rise mt-6 max-w-xl text-base text-muted [--i:2] sm:text-lg">{t("auth.heroSub")}</p>
            <div className="rise mt-8 flex flex-wrap items-center gap-3 [--i:3]">
              <Link to="/register" className="btn-aurora inline-flex items-center gap-2 rounded-2xl px-6 py-3.5 text-base font-semibold">
                <Icon name="sparkle" size={18} />
                {t("landing.start")}
              </Link>
              <Link to="/login" className="inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/[0.04] px-6 py-3.5 text-base font-medium text-ink transition hover:border-white/30 hover:bg-white/[0.08]">
                {t("nav.login")}
              </Link>
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

          <div className="relative mx-auto grid w-full max-w-xl grid-cols-2 items-center gap-4" aria-hidden>
            {TILES.map((x, i) => (
              <figure
                key={x.key}
                className={`tile rise spot relative overflow-hidden rounded-[22px] border border-white/10 ${i % 2 ? "translate-y-6" : ""}`}
                style={{ aspectRatio: x.ratio, transform: `rotate(${x.tilt}deg)`, ["--i" as string]: i + 2 }}
              >
                <div
                  className="absolute inset-0 animate-[drift_14s_ease-in-out_infinite_alternate]"
                  style={{ background: `radial-gradient(70% 60% at 25% 20%, ${x.a}, transparent 70%), radial-gradient(60% 60% at 80% 75%, ${x.b}, transparent 70%), ${x.c}` }}
                />
                <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-3 pt-10 text-[11px] leading-snug text-ink/90">
                  {t(`landing.${x.key}`)}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>

        <section id="features" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6">
          <h2 className="max-w-2xl text-3xl font-bold tracking-tight sm:text-5xl">{t("landing.featuresTitle")}</h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <article key={f.key} className="glass spot rise rounded-[var(--radius-card)] p-6" style={{ ["--i" as string]: i }}>
                <span className="mb-4 grid h-11 w-11 place-items-center rounded-2xl border border-white/10 bg-white/[0.04] text-accent">
                  <Icon name={f.icon} size={20} />
                </span>
                <h3 className="font-display text-lg font-bold tracking-tight">{t(`landing.f_${f.key}`)}</h3>
                <p className="mt-1.5 text-sm text-muted">{t(`landing.f_${f.key}_desc`)}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="how" className="mx-auto max-w-7xl scroll-mt-20 px-4 py-16 sm:px-6">
          <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">{t("landing.howTitle")}</h2>
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

        <section className="mx-auto max-w-7xl px-4 pb-20 pt-8 sm:px-6">
          <div className="glass ring-aurora spot rounded-[32px] px-6 py-14 text-center sm:px-12">
            <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight sm:text-5xl">{t("landing.ctaTitle")}</h2>
            <p className="mx-auto mt-4 max-w-lg text-muted">{t("auth.bonus")}</p>
            <Link to="/register" className="btn-aurora mt-8 inline-flex items-center gap-2 rounded-2xl px-7 py-3.5 text-base font-semibold">
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
