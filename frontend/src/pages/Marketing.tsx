// SPDX-License-Identifier: AGPL-3.0-or-later
// Marketing helper: product text/photo -> ready ad prompts for 9:16 (stories/reels) and 1:1 (feed).
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api";
import { Badge, Button, Card, ErrorText, inputClass, Label } from "../components/ui";
import type { Asset, Job, ModelInfo, Provider } from "../types";

interface Idea {
  id: string;
  format: "9:16" | "1:1";
  scene: string;
  prompt: string;
  headline: string;
  cta: string;
}
interface Result {
  source: "ai" | "templates";
  note: string | null;
  ai_available: boolean;
  palette: { hex: string; name: string; share: number }[];
  ideas: Idea[];
}

/** Business presets: fill the form with a typical starting point (texts live in i18n). */
const BUSINESS = ["shop", "cafe", "services", "event"] as const;
const BUSINESS_TONE: Record<(typeof BUSINESS)[number], string> = {
  shop: "friendly",
  cafe: "playful",
  services: "premium",
  event: "bold",
};

type Choice = { p: Provider; m: ModelInfo };

/** Default model for one-click ads: an available image model allowed for commercial use that
 * supports the format, preferring free providers, then the lowest credit cost. */
export function pickAdModel(providers: Provider[], aspect: string): Choice | undefined {
  const all = providers
    .filter((p) => p.available)
    .flatMap((p) => p.models.map((m) => ({ p, m })))
    .filter(({ m }) => m.kind === "image" && m.commercial_use === "yes" && m.aspect_ratios.includes(aspect));
  const rank = ({ p, m }: Choice) => (p.tier === "free" ? 0 : 1_000_000) + m.credit_cost;
  return all.sort((a, b) => rank(a) - rank(b))[0];
}

function CopyButton({ text }: { text: string }) {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="text-[11px] text-muted hover:text-accent"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        } catch {
          /* clipboard blocked */
        }
      }}
    >
      {done ? `✓ ${t("marketing.copied")}` : `⧉ ${t("marketing.copy")}`}
    </button>
  );
}

export default function Marketing() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { reload } = useAuth();
  const [form, setForm] = useState({
    product: "",
    description: "",
    audience: "",
    tone: "friendly",
    language: (["en", "uz", "ru"].includes(i18n.language) ? i18n.language : "en") as string,
    per_format: 3,
  });
  const [photo, setPhoto] = useState<Asset | null>(null);
  const [useAi, setUseAi] = useState(false);
  const [providers, setProviders] = useState<Provider[]>([]);
  const aiReady = providers.some((p) => p.id === "cloudflare" && p.available);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [sent, setSent] = useState<Record<string, "busy" | "sent">>({});
  const [confirmAll, setConfirmAll] = useState(false);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api<Provider[]>("/api/providers")
      .then(setProviders)
      .catch(() => setProviders([]));
  }, []);

  const models = useMemo(
    () => ({ "9:16": pickAdModel(providers, "9:16"), "1:1": pickAdModel(providers, "1:1") }),
    [providers],
  );
  const pending = (result?.ideas ?? []).filter((i) => sent[i.id] !== "sent" && models[i.format]);
  const totalCost = pending.reduce((sum, i) => sum + (models[i.format]?.m.credit_cost ?? 0), 0);

  const applyBusiness = (b: (typeof BUSINESS)[number]) =>
    setForm({
      ...form,
      product: t(`marketing.biz_${b}_product`),
      description: t(`marketing.biz_${b}_desc`),
      audience: t(`marketing.biz_${b}_audience`),
      tone: BUSINESS_TONE[b],
    });

  const upload = async (file: File) => {
    setError(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      setPhoto(await api<Asset>("/api/assets/upload", { method: "POST", form: fd }));
    } catch (e) {
      setError(e);
    }
  };

  const generate = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<Result>("/api/marketing/ideas", {
        method: "POST",
        body: { ...form, image_asset_id: photo?.id ?? null, use_ai: useAi && aiReady },
      });
      setResult(r);
      setEdits({});
      setSent({});
      setConfirmAll(false);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const promptOf = (i: Idea) => edits[i.id] ?? i.prompt;
  /** Create one image job for an idea with the default model; false if it failed (error shown). */
  const createJob = async (i: Idea): Promise<boolean> => {
    const choice = models[i.format];
    if (!choice) return false;
    setSent((s) => ({ ...s, [i.id]: "busy" }));
    try {
      await api<Job>("/api/jobs", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: { prompt: promptOf(i), provider: choice.p.id, model: choice.m.id, aspect_ratio: i.format, size: "large", count: 1 },
      });
      setSent((s) => ({ ...s, [i.id]: "sent" }));
      return true;
    } catch (err) {
      setError(err);
      setSent((s) => {
        const { [i.id]: _drop, ...rest } = s;
        return rest;
      });
      return false;
    }
  };

  const generateOne = async (i: Idea) => {
    setError(null);
    await createJob(i);
    void reload();
  };

  const generateAll = async () => {
    setConfirmAll(false);
    setRunning(true);
    setError(null);
    for (const i of pending) {
      if (!(await createJob(i))) break; // stop on the first error (credits, limits)
    }
    setRunning(false);
    void reload();
  };

  const openInStudio = (i: Idea, animate = false) =>
    navigate("/create", {
      state: animate && photo
        ? { animate: photo, prefill: { prompt: promptOf(i), aspect: i.format } }
        : { prefill: { prompt: promptOf(i), aspect: i.format } },
    });

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      <Card className="h-fit lg:sticky lg:top-6">
        <h1 className="text-2xl tracking-[0.02em]">{t("marketing.title")}</h1>
        <p className="mt-1 text-xs text-muted">{t("marketing.subtitle")}</p>
        <form onSubmit={generate} className="mt-4 space-y-3">
          <div>
            <Label>{t("marketing.business")}</Label>
            <div className="flex flex-wrap gap-1.5">
              {BUSINESS.map((b) => (
                <button
                  key={b}
                  type="button"
                  onClick={() => applyBusiness(b)}
                  className="rounded-full border border-line bg-bg/60 px-3 py-1 text-xs font-medium text-ink transition hover:border-accent hover:text-accent"
                >
                  {t(`marketing.biz_${b}`)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <Label htmlFor="mk-product">{t("marketing.product")}</Label>
            <input id="mk-product" required minLength={2} maxLength={80} value={form.product} onChange={(e) => setForm({ ...form, product: e.target.value })} placeholder={t("marketing.productPh")} className={inputClass} />
          </div>
          <div>
            <Label htmlFor="mk-desc">{t("marketing.description")}</Label>
            <textarea id="mk-desc" rows={3} maxLength={400} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder={t("marketing.descriptionPh")} className={inputClass} />
          </div>
          <div>
            <Label htmlFor="mk-aud">{t("marketing.audience")}</Label>
            <input id="mk-aud" maxLength={80} value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })} placeholder={t("marketing.audiencePh")} className={inputClass} />
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div>
              <Label htmlFor="mk-tone">{t("marketing.tone")}</Label>
              <select id="mk-tone" value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })} className={inputClass}>
                {["friendly", "premium", "playful", "bold"].map((v) => (
                  <option key={v} value={v}>{t(`marketing.tone_${v}`)}</option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="mk-lang">{t("marketing.copyLanguage")}</Label>
              <select id="mk-lang" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} className={inputClass}>
                <option value="uz">{t("marketing.langUz")}</option>
                <option value="ru">{t("marketing.langRu")}</option>
                <option value="en">{t("marketing.langEn")}</option>
              </select>
            </div>
            <div>
              <Label htmlFor="mk-n">{t("marketing.perFormat")}</Label>
              <select id="mk-n" value={form.per_format} onChange={(e) => setForm({ ...form, per_format: Number(e.target.value) })} className={inputClass}>
                {[2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          </div>
          <div>
            <Label>{t("marketing.photo")}</Label>
            {photo ? (
              <div className="flex items-center gap-3 rounded-xl border border-line bg-bg/60 p-2">
                <img src={photo.preview_url || photo.url} alt="" className="h-14 w-14 rounded object-cover" />
                <span className="flex-1 text-[11px] text-muted">{t("marketing.photoHint")}</span>
                <button type="button" onClick={() => setPhoto(null)} className="text-xs text-muted hover:text-ink">✕</button>
              </div>
            ) : (
              <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} className="block w-full text-xs text-muted file:mr-3 file:rounded-md file:border-0 file:bg-raised file:px-3 file:py-1.5 file:text-ink" />
            )}
          </div>
          <label className="flex items-start gap-2 text-xs">
            <input type="checkbox" checked={useAi && aiReady} disabled={!aiReady} onChange={(e) => setUseAi(e.target.checked)} className="mt-0.5" />
            <span>
              {t("marketing.useAi")}
              <span className="block text-[11px] text-muted">
                {aiReady ? t("marketing.useAiHint") : <>{t("marketing.useAiNeedsKey")} <Link to="/settings" className="underline">{t("nav.settings")}</Link></>}
              </span>
            </span>
          </label>
          <Button type="submit" className="w-full" disabled={busy || form.product.trim().length < 2}>
            {busy ? t("marketing.working") : result ? t("marketing.regenerate") : t("marketing.generate")}
          </Button>
          <ErrorText error={error} />
        </form>
      </Card>

      <div className="space-y-4">
        {!result && <Card className="text-sm text-muted">{t("marketing.empty")}</Card>}
        {result && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge tone={result.source === "ai" ? "ok" : "muted"}>{result.source === "ai" ? t("marketing.sourceAi") : t("marketing.sourceTemplates")}</Badge>
              {result.note === "ai_failed" && <span className="text-accent">{t("marketing.aiFailed")}</span>}
              {result.palette.map((c) => (
                <span key={c.hex} className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-muted" title={`${c.hex} · ${c.share}%`}>
                  <span className="inline-block h-3 w-3 rounded-full border border-line" style={{ background: c.hex }} />
                  {c.name}
                </span>
              ))}
            </div>
            <Card className="flex flex-wrap items-center gap-3 p-4 text-sm">
              {pending.length === 0 ? (
                <span className="text-muted">
                  {Object.values(sent).includes("sent") ? (
                    <>{t("marketing.allSent")} <Link to="/create" className="underline hover:text-accent">{t("marketing.seeResults")}</Link></>
                  ) : (
                    t("marketing.noModel")
                  )}
                </span>
              ) : confirmAll ? (
                <>
                  <span className="flex-1">{t("marketing.confirmAll", { count: pending.length, credits: totalCost })}</span>
                  <Button className="px-3 py-1.5 text-xs" onClick={() => void generateAll()}>{t("marketing.confirm")}</Button>
                  <Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={() => setConfirmAll(false)}>{t("marketing.cancel")}</Button>
                </>
              ) : (
                <>
                  <span className="flex-1 text-muted">{t("marketing.allCost", { count: pending.length, credits: totalCost })}</span>
                  <Button className="px-3 py-1.5 text-xs" disabled={running} onClick={() => setConfirmAll(true)}>
                    {running ? t("marketing.working") : t("marketing.generateAll")}
                  </Button>
                </>
              )}
            </Card>
            {(["9:16", "1:1"] as const).map((fmt) => (
              <section key={fmt}>
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">
                  {fmt} · {t(fmt === "9:16" ? "marketing.vertical" : "marketing.square")}
                </h2>
                <div className="grid gap-3 md:grid-cols-2">
                  {result.ideas.filter((i) => i.format === fmt).map((i) => (
                    <Card key={i.id} className="p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <Badge tone="muted">{t(`marketing.scene_${i.scene}`, { defaultValue: i.scene })}</Badge>
                        <span className={`inline-block rounded border border-line ${fmt === "9:16" ? "h-7 w-4" : "h-5 w-5"}`} aria-hidden />
                      </div>
                      <p className="text-base font-semibold leading-snug">{i.headline}</p>
                      <div className="mt-1 flex items-center gap-2">
                        <Badge tone="paid">{i.cta}</Badge>
                        <CopyButton text={`${i.headline}\n${i.cta}`} />
                      </div>
                      <Label htmlFor={`p-${i.id}`}>{t("marketing.imagePrompt")}</Label>
                      <textarea id={`p-${i.id}`} rows={4} value={promptOf(i)} onChange={(e) => setEdits({ ...edits, [i.id]: e.target.value })} className={`${inputClass} text-xs`} />
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {sent[i.id] === "sent" ? (
                          <Link to="/create" className="text-xs font-semibold text-accent hover:underline">✓ {t("marketing.sent")}</Link>
                        ) : (
                          models[fmt] && (
                            <Button className="px-3 py-1.5 text-xs" disabled={running || sent[i.id] === "busy"} onClick={() => void generateOne(i)}>
                              {sent[i.id] === "busy" ? t("marketing.working") : t("marketing.generateOne", { count: models[fmt]!.m.credit_cost })}
                            </Button>
                          )
                        )}
                        <Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={() => openInStudio(i)}>{t("marketing.openStudio")}</Button>
                        {photo && fmt === "9:16" && (
                          <Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={() => openInStudio(i, true)}>▶ {t("marketing.animatePhoto")}</Button>
                        )}
                        <CopyButton text={promptOf(i)} />
                      </div>
                    </Card>
                  ))}
                </div>
              </section>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
