// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { nextPath, useAuth } from "../auth";
import { Footer, LanguageSelect, Logo } from "../components/Layout";
import Turnstile, { turnstileEnabled } from "../components/Turnstile";
import { Icon, type IconName } from "../components/icons";
import { Button, ErrorText, inputClass, Label } from "../components/ui";
import type { Locale, User } from "../types";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { t, i18n } = useTranslation();
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accept, setAccept] = useState(false);
  const [captcha, setCaptcha] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const register = mode === "register";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = register
        ? { email, password, accept_terms: accept, locale: i18n.language as Locale, turnstile_token: captcha }
        : { email, password, turnstile_token: captcha };
      const user = await api<User>(`/api/auth/${mode}`, { method: "POST", body });
      setUser(user);
      const prefill = (location.state as { prefill?: unknown } | null)?.prefill;
      navigate(nextPath(location.state), prefill ? { state: { prefill } } : undefined);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const features: { icon: IconName; key: string }[] = [
    { icon: "layers", key: "models" },
    { icon: "video", key: "video" },
    { icon: "expand", key: "upscale" },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
        <Logo />
        <LanguageSelect />
      </div>
      <main className="mx-auto grid w-full max-w-7xl flex-1 items-center gap-10 px-4 pb-10 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
        <section className="hidden lg:block">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-surface-1 px-3.5 py-1 text-xs font-semibold text-accent">
            <Icon name="sparkle" size={13} />
            {t("auth.heroEyebrow")}
          </p>
          <h2 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
            {t("auth.heroLead")}{" "}
            <span className="text-accent block pt-1 font-semibold">{t("auth.heroAccent")}</span>
          </h2>
          <p className="mt-4 max-w-lg text-sm text-muted leading-relaxed">{t("auth.heroSub")}</p>
          <ul className="mt-8 space-y-4">
            {features.map((f) => (
              <li key={f.key} className="flex items-start gap-3.5">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-line bg-surface-1 text-accent">
                  <Icon name={f.icon} size={18} />
                </span>
                <div>
                  <span className="block text-sm font-semibold text-ink">{t(`auth.feat_${f.key}`)}</span>
                  <span className="block text-xs text-muted mt-0.5">{t(`auth.feat_${f.key}_desc`)}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="mx-auto w-full max-w-md">
          <div className="rounded-3xl border border-line bg-surface-1 p-6 sm:p-8 shadow-2xl">
            <h1 className="text-2xl font-bold tracking-tight">
              {register ? t("auth.registerTitle") : t("auth.loginTitle")}
            </h1>
            <p className="mt-1 text-xs text-muted">{register ? t("auth.bonus") : t("app.tagline")}</p>
            <form onSubmit={submit} className="mt-6 space-y-4">
              <div>
                <Label htmlFor="email">{t("auth.email")}</Label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <Label htmlFor="password">{t("auth.password")}</Label>
                <input
                  id="password"
                  type="password"
                  autoComplete={register ? "new-password" : "current-password"}
                  required
                  minLength={register ? 10 : 1}
                  maxLength={128}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass}
                />
                {register && <p className="mt-1.5 text-[11px] text-muted">{t("auth.passwordHint")}</p>}
              </div>
              {register && (
                <label className="flex items-start gap-2.5 text-xs text-muted cursor-pointer select-none">
                  <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="mt-0.5 h-4 w-4 accent-white rounded" />
                  <span>
                    {t("auth.acceptTerms")} ·{" "}
                    <Link to="/terms" className="underline hover:text-ink">{t("auth.readTerms")}</Link>
                  </span>
                </label>
              )}
              <Turnstile onToken={setCaptcha} />
              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={busy || (register && !accept) || (turnstileEnabled && !captcha)}
              >
                {register ? t("auth.register") : t("auth.login")}
              </Button>
              <ErrorText error={error} />
            </form>
            <p className="mt-6 text-center text-xs text-muted">
              {register ? t("auth.haveAccount") : t("auth.noAccount")}{" "}
              <Link to={register ? "/login" : "/register"} state={location.state} className="font-semibold text-accent hover:underline">
                {register ? t("nav.login") : t("nav.register")}
              </Link>
            </p>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
