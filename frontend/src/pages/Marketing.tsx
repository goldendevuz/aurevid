// SPDX-License-Identifier: AGPL-3.0-or-later
// Marketing helper: product text/photo -> ready ad prompts for 9:16 (stories/reels) and 1:1 (feed).
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { Badge, Button, Card, ErrorText, inputClass, Label } from "../components/ui";
import type { Asset, Provider } from "../types";

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
  const [aiReady, setAiReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});

  useEffect(() => {
    api<Provider[]>("/api/providers")
      .then((ps) => setAiReady(ps.some((p) => p.id === "cloudflare" && p.available)))
      .catch(() => setAiReady(false));
  }, []);

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
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const promptOf = (i: Idea) => edits[i.id] ?? i.prompt;
  const openInStudio = (i: Idea, animate = false) =>
    navigate("/", {
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
                <option value="uz">O'zbekcha</option>
                <option value="ru">Русский</option>
                <option value="en">English</option>
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
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Button className="px-3 py-1.5 text-xs" onClick={() => openInStudio(i)}>{t("marketing.openStudio")}</Button>
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
