// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Footer, LanguageSelect, Logo } from "../components/Layout";
import { Icon } from "../components/icons";
import ModelMarquee from "../components/ModelMarquee";

/** 10 sample outputs using Aurevid's built-in media files and gradients */
const SAMPLE_WALL = [
  {
    id: "s1",
    title: "Golden Leaf Descent",
    model: "Wan 2.1 Video",
    kind: "video",
    src: "/samples/golden_leaf.mp4",
    aspect: "16:9",
    prompt: "A single golden leaf falls slowly through soft morning light, spinning gently as it descends against a blurred forest background, high cinematic motion, 24fps",
  },
  {
    id: "s2",
    title: "Cyber Synth Highway",
    model: "Seedance 2.5",
    kind: "video",
    src: "/samples/cyber_synth.mp4",
    aspect: "16:9",
    prompt: "80s synthwave neon highway at sunset, digital wireframe horizon grid, vibrant magenta and cyan glow, retrofuturism aesthetic, endless drive",
  },
  {
    id: "s3",
    title: "Aurora Drift Particles",
    model: "Kling 1.5",
    kind: "video",
    src: "/samples/aurora_drift.mp4",
    aspect: "16:10",
    prompt: "Atmospheric aurora borealis ribbons dancing across Arctic night sky, cosmic glow, hyper-detail, slow fluid particle movement",
  },
  {
    id: "s4",
    title: "Astronaut in Sakura Bloom",
    model: "FLUX.1 Schnell",
    kind: "image",
    gradient: "linear-gradient(135deg, #1e1b4b, #4338ca, #ec4899)",
    aspect: "1:1",
    prompt: "Astronaut meditating under glowing pink Japanese cherry blossom trees on an alien planet, cinematic 8K, volumetric lighting",
  },
  {
    id: "s5",
    title: "Emerald Forest Sanctuary",
    model: "FLUX.1 Pro",
    kind: "image",
    gradient: "linear-gradient(135deg, #064e3b, #047857, #10b981)",
    aspect: "4:3",
    prompt: "Ancient mossy forest shrine with morning rays filtering through dense canopy, hyperrealistic texture, octane render",
  },
  {
    id: "s6",
    title: "Solar Flare Cityscape",
    model: "Seedance 2.5",
    kind: "video",
    src: "/samples/cyber_synth.mp4",
    aspect: "16:9",
    prompt: "Futuristic skyscrapers reflecting golden sunset rays, flying drones and sleek glass architectural towers, photorealistic",
  },
  {
    id: "s7",
    title: "Obsidian Crystal Cavern",
    model: "FLUX.1 Dev",
    kind: "image",
    gradient: "linear-gradient(135deg, #0f172a, #334155, #64748b)",
    aspect: "3:4",
    prompt: "Giant geometric obsidian crystals embedded in dark volcanic basalt, subtle blue luminescence, ultra-detailed micro-surface",
  },
  {
    id: "s8",
    title: "Bioluminescent Jellyfish Horizon",
    model: "Wan 2.1",
    kind: "video",
    src: "/samples/aurora_drift.mp4",
    aspect: "16:9",
    prompt: "Floating translucent deep-sea jellyfish floating through twilight skies above calm ocean waters, bioluminescent tentacles",
  },
  {
    id: "s9",
    title: "Desert Sandstorm Mirage",
    model: "FLUX.1 Schnell",
    kind: "image",
    gradient: "linear-gradient(135deg, #451a03, #9a3412, #f59e0b)",
    aspect: "16:9",
    prompt: "Endless golden dunes under heat distortion waves, distant futuristic nomad caravan with reflective solar sails",
  },
  {
    id: "s10",
    title: "Deep Space Quantum Core",
    model: "Seedance 2.5",
    kind: "video",
    src: "/samples/golden_leaf.mp4",
    aspect: "16:9",
    prompt: "Spinning spherical Dyson sphere fragment channeling plasma energy, intricate mechanical surface panels, dark starfield backdrop",
  },
];

export default function Landing() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [heroPrompt, setHeroPrompt] = useState("");

  const handlePromptSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!heroPrompt.trim()) {
      navigate("/create");
      return;
    }
    navigate("/create", { state: { prefill: { prompt: heroPrompt.trim(), aspect: "16:9" } } });
  };

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 border-b border-line bg-surface-1/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Logo />
          <nav aria-label="Main navigation" className="hidden items-center gap-1 md:flex">
            <Link to="/create" className="rounded-full px-3.5 py-1.5 text-sm font-medium text-muted hover:text-ink hover:bg-surface-2 transition">
              Create
            </Link>
            <Link to="/pricing" className="rounded-full px-3.5 py-1.5 text-sm font-medium text-muted hover:text-ink hover:bg-surface-2 transition">
              Pricing
            </Link>
            <a href="#how" className="rounded-full px-3.5 py-1.5 text-sm font-medium text-muted hover:text-ink hover:bg-surface-2 transition">
              How it works
            </a>
            <a href="#samples" className="rounded-full px-3.5 py-1.5 text-sm font-medium text-muted hover:text-ink hover:bg-surface-2 transition">
              Showcase
            </a>
          </nav>
          <div className="flex items-center gap-2.5">
            <LanguageSelect />
            {!loading && (
              user ? (
                <Link
                  to="/create"
                  className="rounded-full bg-accent px-4 py-1.5 text-xs font-semibold text-accent-ink hover:bg-accent/90 transition"
                >
                  Open Studio
                </Link>
              ) : (
                <>
                  <Link to="/login" className="rounded-full px-3.5 py-1.5 text-xs font-medium text-muted hover:text-ink transition">
                    Sign in
                  </Link>
                  <Link
                    to="/register"
                    className="rounded-full bg-accent px-4 py-1.5 text-xs font-semibold text-accent-ink hover:bg-accent/90 transition"
                  >
                    Get Started
                  </Link>
                </>
              )
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* HERO SECTION */}
        <section className="relative px-4 pb-16 pt-12 sm:px-6 sm:pb-24 sm:pt-20 text-center max-w-5xl mx-auto">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-surface-1 px-3.5 py-1 text-xs font-semibold text-accent">
            <Icon name="sparkle" size={13} />
            Next-Generation Creative AI Studio
          </div>

          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.05]">
            Transform Imagination Into <br className="hidden sm:inline" />
            <span className="text-accent">Cinematic Video & Images</span>
          </h1>

          <p className="mt-4 max-w-2xl mx-auto text-base sm:text-lg text-muted">
            The multi-provider AI studio that brings Seedance 2.5, FLUX, Wan 2.1, Kling and OpenRouter frontier models under one unified, privacy-first interface.
          </p>

          {/* Prompt Entry Input (redirects to /create with text prefilled) */}
          <form onSubmit={handlePromptSubmit} className="mt-8 max-w-2xl mx-auto">
            <div className="relative flex items-center rounded-2xl border border-line bg-surface-1 p-2 shadow-2xl focus-within:border-accent/60 transition">
              <Icon name="sparkle" size={18} className="ml-3 text-muted shrink-0" />
              <input
                type="text"
                value={heroPrompt}
                onChange={(e) => setHeroPrompt(e.target.value)}
                placeholder="Describe your scene (e.g. A cybernetic tiger walking in neon rain...)"
                className="w-full bg-transparent px-3 py-2 text-sm text-ink placeholder:text-muted/60 focus:outline-none"
              />
              <button
                type="submit"
                className="shrink-0 rounded-xl bg-accent px-5 py-2.5 text-xs font-semibold text-accent-ink hover:bg-accent/90 transition flex items-center gap-1.5"
              >
                <span>Generate</span>
                <span aria-hidden>→</span>
              </button>
            </div>
            <p className="mt-2 text-[11px] text-muted">
              Press enter or click generate to open the studio with your prompt ready.
            </p>
          </form>

          {/* 3 "Start Here" Cards */}
          <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-4 text-left max-w-4xl mx-auto">
            {/* Card 1: Image */}
            <Link
              to="/create?mode=image"
              className="group rounded-2xl border border-line bg-surface-1 p-5 hover:border-accent/50 hover:bg-surface-2 transition flex flex-col justify-between"
            >
              <div>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-surface-2 text-accent group-hover:bg-accent/15 transition">
                  <Icon name="image" size={20} />
                </span>
                <h3 className="mt-3 text-base font-semibold text-ink group-hover:text-accent transition">
                  Image Generation
                </h3>
                <p className="mt-1 text-xs text-muted leading-relaxed">
                  Ultra-sharp stills with FLUX.1 Schnell, Dev & Pro. Instant 4K upscaling and multi-image compare.
                </p>
              </div>
              <span className="mt-4 text-xs font-medium text-accent flex items-center gap-1">
                Start with Image <span aria-hidden>→</span>
              </span>
            </Link>

            {/* Card 2: Video */}
            <Link
              to="/create?mode=video"
              className="group rounded-2xl border border-line bg-surface-1 p-5 hover:border-accent/50 hover:bg-surface-2 transition flex flex-col justify-between"
            >
              <div>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-surface-2 text-accent group-hover:bg-accent/15 transition">
                  <Icon name="video" size={20} />
                </span>
                <h3 className="mt-3 text-base font-semibold text-ink group-hover:text-accent transition">
                  Video Clips
                </h3>
                <p className="mt-1 text-xs text-muted leading-relaxed">
                  Cinematic text-to-video & image-to-video with Seedance 2.5, Wan 2.1, Kling, and native audio support.
                </p>
              </div>
              <span className="mt-4 text-xs font-medium text-accent flex items-center gap-1">
                Start with Video <span aria-hidden>→</span>
              </span>
            </Link>

            {/* Card 3: Multi-scene Stories */}
            <Link
              to="/create?mode=video&scene=multi"
              className="group rounded-2xl border border-line bg-surface-1 p-5 hover:border-accent/50 hover:bg-surface-2 transition flex flex-col justify-between"
            >
              <div>
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-surface-2 text-accent group-hover:bg-accent/15 transition">
                  <Icon name="layers" size={20} />
                </span>
                <h3 className="mt-3 text-base font-semibold text-ink group-hover:text-accent transition">
                  Multi-Scene Stories
                </h3>
                <p className="mt-1 text-xs text-muted leading-relaxed">
                  Chain sequential video clips into coherent short films with automated stitching and director planning.
                </p>
              </div>
              <span className="mt-4 text-xs font-medium text-accent flex items-center gap-1">
                Build a Story <span aria-hidden>→</span>
              </span>
            </Link>
          </div>
        </section>

        {/* MODEL MARQUEE STRIP */}
        <section className="border-y border-line bg-surface-1/40 py-6">
          <p className="text-center text-xs font-semibold uppercase tracking-wider text-muted mb-4">
            Unified access to world-class generative models
          </p>
          <ModelMarquee />
        </section>

        {/* MEDIA WALL OF AUREVID SAMPLE OUTPUTS */}
        <section id="samples" className="px-4 py-20 sm:px-6 max-w-7xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-1 px-3 py-0.5 text-xs font-semibold text-muted">
              Showcase
            </span>
            <h2 className="mt-2 text-3xl sm:text-4xl font-bold tracking-tight">Crafted With Aurevid</h2>
            <p className="mt-2 text-sm text-muted">
              Explore authentic outputs generated across our multi-provider video and image pipelines.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {SAMPLE_WALL.map((sample) => (
              <div
                key={sample.id}
                className="group relative overflow-hidden rounded-2xl border border-line bg-surface-1 transition hover:border-accent/40"
              >
                <div className="relative aspect-[16/10] overflow-hidden bg-surface-2">
                  {sample.kind === "video" ? (
                    <video
                      src={sample.src}
                      autoPlay
                      muted
                      loop
                      playsInline
                      className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
                    />
                  ) : (
                    <div
                      className="h-full w-full transition duration-300 group-hover:scale-105"
                      style={{ background: sample.gradient }}
                    />
                  )}
                  <span className="absolute left-2.5 top-2.5 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold text-ink backdrop-blur">
                    {sample.model}
                  </span>
                </div>
                <div className="p-3.5">
                  <h4 className="text-xs font-semibold text-ink">{sample.title}</h4>
                  <p className="mt-1 line-clamp-2 text-[11px] text-muted leading-relaxed">
                    "{sample.prompt}"
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate("/create", { state: { prefill: { prompt: sample.prompt, aspect: sample.aspect } } })}
                    className="mt-2 text-[11px] font-medium text-accent hover:underline flex items-center gap-1"
                  >
                    <span>Use this prompt</span>
                    <span aria-hidden>→</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* HOW IT WORKS 3-STEP STRIP */}
        <section id="how" className="border-t border-line bg-surface-1/30 px-4 py-20 sm:px-6">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-12">
              <span className="text-xs font-semibold uppercase tracking-wider text-accent">Simple 3-Step Workflow</span>
              <h2 className="mt-2 text-3xl font-bold tracking-tight">How Aurevid Works</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div className="rounded-2xl border border-line bg-surface-1 p-6">
                <span className="rounded-lg bg-surface-3 px-2.5 py-1 font-mono text-xs font-bold text-accent">01</span>
                <h3 className="mt-4 text-base font-semibold text-ink">Type an Idea or Upload</h3>
                <p className="mt-2 text-xs text-muted leading-relaxed">
                  Input a short prompt or reference frame. Use our built-in Expand prompt engine for instant cinematic enrichment.
                </p>
              </div>
              <div className="rounded-2xl border border-line bg-surface-1 p-6">
                <span className="rounded-lg bg-surface-3 px-2.5 py-1 font-mono text-xs font-bold text-accent">02</span>
                <h3 className="mt-4 text-base font-semibold text-ink">Select Frontier AI Model</h3>
                <p className="mt-2 text-xs text-muted leading-relaxed">
                  Choose from Seedance, FLUX, Wan, Kling, or bring your own OpenRouter key to pay wholesale rates directly.
                </p>
              </div>
              <div className="rounded-2xl border border-line bg-surface-1 p-6">
                <span className="rounded-lg bg-surface-3 px-2.5 py-1 font-mono text-xs font-bold text-accent">03</span>
                <h3 className="mt-4 text-base font-semibold text-ink">Download & Upscale</h3>
                <p className="mt-2 text-xs text-muted leading-relaxed">
                  Watch live streaming generation, upscale directly to 4K, animate stills to video clips, and download water-mark free.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* FREE & OPEN SOURCE STRIP */}
        <section className="border-t border-line px-4 py-16 sm:px-6 text-center">
          <div className="max-w-3xl mx-auto rounded-3xl border border-line bg-surface-1 p-8 sm:p-10">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-2 px-3 py-1 text-xs font-semibold text-accent mb-3">
              <Icon name="shield" size={14} />
              Open Source & Self-Hostable
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold">100% Free and Open Source Under AGPL-3.0</h2>
            <p className="mt-2 text-sm text-muted max-w-xl mx-auto">
              Run Aurevid on your own servers with Docker, connect local GPU backends, or use our cloud platform with no lock-in.
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <a
                href="https://github.com/goldendevuz/aurevid"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-xl bg-surface-2 border border-line px-4 py-2 text-xs font-semibold text-ink hover:border-white/30 transition"
              >
                <Icon name="star" size={14} className="text-accent" />
                Star on GitHub
              </a>
              <Link
                to="/create"
                className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-accent-ink hover:bg-accent/90 transition"
              >
                Try Online Now
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
