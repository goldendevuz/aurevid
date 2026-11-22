// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { Link } from "react-router-dom";
import { BuyCredits } from "../components/BuyCredits";
import { Icon } from "../components/icons";
import { Badge } from "../components/ui";

const FAQS = [
  {
    q: "What happens if a generation fails?",
    a: "Credits are automatically and instantly refunded to your account balance whenever a provider returns an error, times out, or triggers a content moderation block.",
  },
  {
    q: "Can I bring my own API keys (BYOK)?",
    a: "Yes! Connect your OpenRouter or Modal API keys in Settings. When using your own key, you pay the model provider directly at raw API wholesale cost — Aurevid credits are never deducted.",
  },
  {
    q: "Do purchased credits expire?",
    a: "No. All credit packs are permanently valid and remain in your wallet until consumed.",
  },
  {
    q: "Can I use generated images and videos commercially?",
    a: "Yes, for all models marked with the 'Commercial OK' badge (including FLUX Schnell, Wan 2.1, Seedance 2.5, and all BYOK models).",
  },
  {
    q: "What payment methods are supported?",
    a: "We accept local cards (Uzcard, Humo) and international Visa / Mastercard via our secure checkout gateway.",
  },
];

export default function Pricing() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 space-y-12">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-1 px-3.5 py-1 text-xs font-semibold text-accent">
          <Icon name="coins" size={14} />
          Transparent Pricing
        </span>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">Flexible Credit Packs & BYOK</h1>
        <p className="mt-3 text-sm text-muted">
          Pay as you create with credit packs, or connect your own OpenRouter key to generate at zero markup.
        </p>
      </div>

      {/* Credit Packs */}
      <div>
        <h2 className="text-xl font-semibold mb-4 text-center sm:text-left">Credit Packs</h2>
        <BuyCredits onPaid={() => {}} />
      </div>

      {/* What 1 Credit Buys Table */}
      <div className="rounded-3xl border border-line bg-surface-1 p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl font-bold">What 1 Credit Buys</h2>
            <p className="text-xs text-muted mt-0.5">Approximate cost and generation allowances per tier</p>
          </div>
          <Badge tone="live">1 Credit ≈ 1.5¢ – 2.0¢</Badge>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="pb-3 font-semibold">Tier / Output</th>
                <th className="pb-3 font-semibold">Representative Model</th>
                <th className="pb-3 font-semibold">Credit Cost</th>
                <th className="pb-3 font-semibold">Estimated Real Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              <tr>
                <td className="py-3 font-medium text-ink">Image (Standard)</td>
                <td className="py-3 text-muted">FLUX.1 Schnell</td>
                <td className="py-3 font-mono text-accent">1 credit</td>
                <td className="py-3 font-mono text-muted">≈ 1.5¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">Image (Pro 2K)</td>
                <td className="py-3 text-muted">FLUX.1 Pro</td>
                <td className="py-3 font-mono text-accent">3 credits</td>
                <td className="py-3 font-mono text-muted">≈ 5.0¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">Video 5s (Draft 480p)</td>
                <td className="py-3 text-muted">Seedance Mini / Wan 2.1</td>
                <td className="py-3 font-mono text-accent">3 credits</td>
                <td className="py-3 font-mono text-muted">≈ 5.5¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">Video 5s (Standard 720p)</td>
                <td className="py-3 text-muted">Seedance 2.5 / Kling 1.5</td>
                <td className="py-3 font-mono text-accent">8 credits</td>
                <td className="py-3 font-mono text-muted">≈ 14.0¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">Video 5s (Premium 1080p)</td>
                <td className="py-3 text-muted">Seedance 2.5 High-Res</td>
                <td className="py-3 font-mono text-accent">16 credits</td>
                <td className="py-3 font-mono text-muted">≈ 32.0¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">Upscale to 4K</td>
                <td className="py-3 text-muted">RealESRGAN Neural Net</td>
                <td className="py-3 font-mono text-accent">2 credits</td>
                <td className="py-3 font-mono text-muted">≈ 3.0¢</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* BYOK Explainer Card */}
      <div className="rounded-3xl border border-accent/40 bg-accent/[0.04] p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-accent text-black">
              <Icon name="key" size={16} />
            </span>
            <h3 className="text-lg font-bold text-ink">Bring Your Own Key (BYOK)</h3>
          </div>
          <p className="text-xs text-muted max-w-xl leading-relaxed">
            Have your own OpenRouter or Modal account? Connect your personal API key to pay the model provider directly at raw compute cost. Aurevid credits are never deducted when your key is used.
          </p>
        </div>
        <Link
          to="/settings"
          className="shrink-0 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-accent-ink hover:bg-accent/90 transition flex items-center gap-1.5"
        >
          <span>Connect API Key</span>
          <span aria-hidden>→</span>
        </Link>
      </div>

      {/* FAQ Accordion */}
      <div className="rounded-3xl border border-line bg-surface-1 p-6 sm:p-8">
        <h2 className="text-xl font-bold mb-6">Frequently Asked Questions</h2>
        <div className="divide-y divide-line/60">
          {FAQS.map((faq, idx) => {
            const open = openFaq === idx;
            return (
              <div key={idx} className="py-4">
                <button
                  type="button"
                  onClick={() => setOpenFaq(open ? null : idx)}
                  className="flex w-full items-center justify-between text-left gap-4"
                >
                  <span className="text-sm font-semibold text-ink">{faq.q}</span>
                  <Icon
                    name="chevron"
                    size={15}
                    className={`text-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`}
                  />
                </button>
                {open && (
                  <p className="mt-2.5 text-xs text-muted leading-relaxed pr-8">
                    {faq.a}
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
