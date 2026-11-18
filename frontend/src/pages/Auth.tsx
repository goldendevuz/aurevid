// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Footer, LanguageSelect, Logo } from "../components/Layout";
import Turnstile, { turnstileEnabled } from "../components/Turnstile";
import { Icon, type IconName } from "../components/icons";
import { Button, ErrorText, inputClass, Label } from "../components/ui";
import type { Locale, User } from "../types";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { t, i18n } = useTranslation();
  const { setUser } = useAuth();
  const navigate = useNavigate();
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
      navigate("/");
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
    <div className="flex min-h-screen flex-col">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
        <Logo />
        <LanguageSelect />
      </div>
      <main className="mx-auto grid w-full max-w-7xl flex-1 items-center gap-10 px-4 pb-10 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
        <section className="hidden lg:block">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-medium text-muted">
            <Icon name="sparkle" size={13} className="text-accent" />
            {t("auth.heroEyebrow")}
          </p>
          <h2 className="text-5xl font-semibold leading-[1.05] tracking-tight xl:text-6xl">
            {t("auth.heroLead")} <span className="aurora-text">{t("auth.heroAccent")}</span>
          </h2>
          <p className="mt-5 max-w-lg text-base text-muted">{t("auth.heroSub")}</p>
          <ul className="mt-8 space-y-4">
            {features.map((f) => (
              <li key={f.key} className="flex items-start gap-3.5">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-accent">
                  <Icon name={f.icon} size={19} />
                </span>
                <span>
                  <span className="block text-sm font-semibold">{t(`auth.feat_${f.key}`)}</span>
                  <span className="block text-sm text-muted">{t(`auth.feat_${f.key}_desc`)}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
        <section className="mx-auto w-full max-w-md">
          <div className="glass ring-aurora rounded-[28px] p-6 sm:p-8">
            <h1 className="text-2xl font-semibold tracking-tight">
              {register ? t("auth.registerTitle") : t("auth.loginTitle")}
            </h1>
            <p className="mt-1.5 text-sm text-muted">{register ? t("auth.bonus") : t("app.tagline")}</p>
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
                <label className="flex items-start gap-2.5 text-xs text-muted">
                  <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="mt-0.5 h-4 w-4 accent-white" />
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
              <Link to={register ? "/login" : "/register"} className="font-semibold text-accent hover:underline">
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
