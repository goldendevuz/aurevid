// SPDX-License-Identifier: AGPL-3.0-or-later
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { LANGUAGES } from "../i18n";
import type { Locale, User } from "../types";

const SOURCE_URL = import.meta.env.VITE_SOURCE_URL as string | undefined;

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
        <path d="M16 6 7 26h4.2l1.9-4.6h5.8l1.9 4.6H25L16 6Zm0 7.4 2 5H14l2-5Z" fill="#f0a73a" />
        <circle cx="24.5" cy="8.5" r="2.5" fill="#f0a73a" />
      </svg>
      aurevid
    </Link>
  );
}

export function LanguageSelect() {
  const { t, i18n } = useTranslation();
  const { user, setUser } = useAuth();
  const change = async (lng: Locale) => {
    await i18n.changeLanguage(lng);
    if (user) setUser(await api<User>("/api/me", { method: "PATCH", body: { locale: lng } }));
  };
  return (
    <select
      aria-label={t("nav.language")}
      value={i18n.language}
      onChange={(e) => void change(e.target.value as Locale)}
      className="rounded-md border border-line bg-bg px-2 py-1 text-xs text-ink"
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}

export default function Layout() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-1.5 text-sm ${isActive ? "bg-raised text-ink" : "text-muted hover:text-ink"}`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
          <Logo />
          <nav className="flex flex-wrap gap-1">
            <NavLink to="/" end className={link}>{t("nav.studio")}</NavLink>
            <NavLink to="/history" className={link}>{t("nav.history")}</NavLink>
            <NavLink to="/usage" className={link}>{t("nav.usage")}</NavLink>
            <NavLink to="/settings" className={link}>{t("nav.settings")}</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {user && (
              <Link to="/usage" className="rounded-full bg-amber/15 px-3 py-1 text-xs font-semibold text-amber">
                {t("nav.credits", { count: user.credit_balance })}
              </Link>
            )}
            <LanguageSelect />
            <button
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              className="text-xs text-muted hover:text-ink"
            >
              {t("nav.logout")}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

export function Footer() {
  const { t } = useTranslation();
  return (
    <footer className="border-t border-line py-4 text-center text-xs text-muted">
      <Link to="/terms" className="hover:text-ink">{t("nav.terms")}</Link>
      <span className="mx-2">·</span>
      {SOURCE_URL ? (
        <a href={SOURCE_URL} rel="noopener noreferrer" target="_blank" className="hover:text-ink">
          Source code (AGPL-3.0)
        </a>
      ) : (
        <span>AGPL-3.0</span>
      )}
    </footer>
  );
}
