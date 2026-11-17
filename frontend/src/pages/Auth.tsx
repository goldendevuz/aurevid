// SPDX-License-Identifier: AGPL-3.0-or-later
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Footer, LanguageSelect, Logo } from "../components/Layout";
import Turnstile, { turnstileEnabled } from "../components/Turnstile";
import { Button, Card, ErrorText, inputClass, Label } from "../components/ui";
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

  return (
    <div className="flex min-h-screen flex-col">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4">
        <Logo />
        <LanguageSelect />
      </div>
      <main className="flex flex-1 items-center justify-center px-4">
        <Card className="w-full max-w-sm">
          <h1 className="text-xl font-semibold tracking-tight">
            {register ? t("auth.registerTitle") : t("auth.loginTitle")}
          </h1>
          <p className="mt-1 text-sm text-muted">{register ? t("auth.bonus") : t("app.tagline")}</p>
          <form onSubmit={submit} className="mt-5 space-y-4">
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
              {register && <p className="mt-1 text-[11px] text-muted">{t("auth.passwordHint")}</p>}
            </div>
            {register && (
              <label className="flex items-start gap-2 text-xs text-muted">
                <input type="checkbox" checked={accept} onChange={(e) => setAccept(e.target.checked)} className="mt-0.5" />
                <span>
                  {t("auth.acceptTerms")} ·{" "}
                  <Link to="/terms" className="underline hover:text-ink">{t("auth.readTerms")}</Link>
                </span>
              </label>
            )}
            <Turnstile onToken={setCaptcha} />
            <Button
              type="submit"
              className="w-full"
              disabled={busy || (register && !accept) || (turnstileEnabled && !captcha)}
            >
              {register ? t("auth.register") : t("auth.login")}
            </Button>
            <ErrorText error={error} />
          </form>
          <p className="mt-5 text-center text-xs text-muted">
            {register ? t("auth.haveAccount") : t("auth.noAccount")}{" "}
            <Link to={register ? "/login" : "/register"} className="text-amber hover:underline">
              {register ? t("nav.login") : t("nav.register")}
            </Link>
          </p>
        </Card>
      </main>
      <Footer />
    </div>
  );
}
