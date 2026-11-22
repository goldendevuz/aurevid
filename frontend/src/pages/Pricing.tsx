import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 space-y-12">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-1 px-3.5 py-1 text-xs font-semibold text-accent">
          <Icon name="coins" size={14} />
          {t("pricing.title")}
        </span>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">{t("pricing.heroEyebrow")}</h1>
        <p className="mt-3 text-sm text-muted">
          {t("pricing.heroSub")}
        </p>
      </div>

      {/* Credit Packs */}
      <div>
        <h2 className="text-xl font-semibold mb-4 text-center sm:text-left">{t("pricing.packsTitle")}</h2>
        <BuyCredits onPaid={() => {}} />
      </div>

      {/* What 1 Credit Buys Table */}
      <div className="rounded-3xl border border-line bg-surface-1 p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl font-bold">{t("pricing.tableTitle")}</h2>
            <p className="text-xs text-muted mt-0.5">{t("pricing.tableSubtitle")}</p>
          </div>
          <Badge tone="live">{t("pricing.creditRate")}</Badge>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="pb-3 font-semibold">{t("pricing.colTier")}</th>
                <th className="pb-3 font-semibold">{t("pricing.colModel")}</th>
                <th className="pb-3 font-semibold">{t("pricing.colCreditCost")}</th>
                <th className="pb-3 font-semibold">{t("pricing.colRealCost")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              <tr>
                <td className="py-3 font-medium text-ink">{t("pricing.tierImageStandard")}</td>
                <td className="py-3 text-muted">{t("pricing.modelFluxSchnell")}</td>
                <td className="py-3 font-mono text-accent">{t("pricing.cost1Credit")}</td>
                <td className="py-3 font-mono text-muted">≈ 1.5¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">{t("pricing.tierImagePro")}</td>
                <td className="py-3 text-muted">{t("pricing.modelFluxPro")}</td>
                <td className="py-3 font-mono text-accent">{t("pricing.cost3Credits")}</td>
                <td className="py-3 font-mono text-muted">≈ 5.0¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">{t("pricing.tierVideoDraft")}</td>
                <td className="py-3 text-muted">{t("pricing.modelSeedanceMini")}</td>
                <td className="py-3 font-mono text-accent">{t("pricing.cost3Credits")}</td>
                <td className="py-3 font-mono text-muted">≈ 5.5¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">{t("pricing.tierVideoStandard")}</td>
                <td className="py-3 text-muted">{t("pricing.modelSeedance25")}</td>
                <td className="py-3 font-mono text-accent">{t("pricing.cost8Credits")}</td>
                <td className="py-3 font-mono text-muted">≈ 14.0¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">{t("pricing.tierVideoPremium")}</td>
                <td className="py-3 text-muted">{t("pricing.modelSeedanceHighRes")}</td>
                <td className="py-3 font-mono text-accent">{t("pricing.cost16Credits")}</td>
                <td className="py-3 font-mono text-muted">≈ 32.0¢</td>
              </tr>
              <tr>
                <td className="py-3 font-medium text-ink">{t("pricing.tierUpscale")}</td>
                <td className="py-3 text-muted">{t("pricing.modelRealEsrgan")}</td>
                <td className="py-3 font-mono text-accent">{t("pricing.cost2Credits")}</td>
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
            <h3 className="text-lg font-bold text-ink">{t("pricing.byokTitle")}</h3>
          </div>
          <p className="text-xs text-muted max-w-xl leading-relaxed">
            {t("pricing.byokBody")}
          </p>
        </div>
        <Link
          to="/settings"
          className="shrink-0 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-accent-ink hover:bg-accent/90 transition flex items-center gap-1.5"
        >
          <span>{t("pricing.byokAction")}</span>
          <span aria-hidden>→</span>
        </Link>
      </div>

      {/* FAQ Accordion */}
      <div className="rounded-3xl border border-line bg-surface-1 p-6 sm:p-8">
        <h2 className="text-xl font-bold mb-6">{t("pricing.faqTitle")}</h2>
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
                  <span className="text-sm font-semibold text-ink">{t(`pricing.faq${idx + 1}_q`, { defaultValue: faq.q })}</span>
                  <Icon
                    name="chevron"
                    size={15}
                    className={`text-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`}
                  />
                </button>
                {open && (
                  <p className="mt-2.5 text-xs text-muted leading-relaxed pr-8">
                    {t(`pricing.faq${idx + 1}_a`, { defaultValue: faq.a })}
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
