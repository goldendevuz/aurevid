// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { LANGUAGES } from "../i18n";
import type { Locale, User } from "../types";
import { Icon, type IconName } from "./icons";

const SOURCE_URL = import.meta.env.VITE_SOURCE_URL as string | undefined;

export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <defs>
        <linearGradient id="av-g" x1="4" y1="28" x2="28" y2="4" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ff3e8a" />
          <stop offset="0.55" stopColor="#ff9a3c" />
          <stop offset="1" stopColor="#ffe08a" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="#1a0b2c" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="8.5" fill="none" stroke="#ff3e8a" strokeOpacity="0.45" />
      <path d="M16 6.5 7.5 25.5h4l1.8-4.4h5.4l1.8 4.4h4L16 6.5Zm0 7.2 1.9 4.7h-3.8l1.9-4.7Z" fill="url(#av-g)" />
      <circle cx="24.6" cy="8.4" r="2.4" fill="url(#av-g)" />
    </svg>
  );
}

/** Goes to "/" and always lands at the top, also when "/" is already open (or has a #hash). */
export function Logo() {
  const { pathname, hash } = useLocation();
  return (
    <Link
      to="/"
      onClick={() => {
        if (pathname === "/" && !hash) window.scrollTo({ top: 0, behavior: "smooth" });
        else window.scrollTo(0, 0);
      }}
      className="flex items-center gap-2.5 text-lg font-semibold tracking-tight">
      <LogoMark />
      <span className="hidden font-display text-xl uppercase tracking-[0.06em] text-white sm:inline">aurevid</span>
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
      className="rounded-lg border border-line bg-bg/70 px-2 py-1.5 text-xs text-ink transition hover:border-white/20"
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
}

export default function Layout({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const items: NavItem[] = [
    { to: "/create", label: t("nav.studio"), icon: "sparkle" },
    { to: "/marketing", label: t("nav.marketing"), icon: "megaphone" },
    { to: "/history", label: t("nav.history"), icon: "history" },
    { to: "/credits", label: t("nav.usage"), icon: "coins" },
    { to: "/settings", label: t("nav.settings"), icon: "settings" },
    ...(user?.is_admin ? [{ to: "/admin", label: t("nav.admin"), icon: "shield" as IconName }] : []),
  ];
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
      isActive ? "btn-aurora" : "text-muted hover:bg-white/[0.06] hover:text-ink"
    }`;
  const tab = ({ isActive }: { isActive: boolean }) =>
    `flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-xl py-1.5 text-[10px] font-medium ${
      isActive ? "neon-text" : "text-muted"
    }`;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 bg-gradient-to-b from-bg via-bg/80 to-transparent">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
          <Logo />
          <nav aria-label="Main" className="glass ml-4 hidden gap-0.5 rounded-full p-1 md:flex">
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.end} className={link}>
                <Icon name={i.icon} size={16} />
                {i.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            {user && (
              <Link
                to="/credits"
                className="glass flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 font-mono text-xs font-semibold text-ink transition hover:border-accent/50"
              >
                <Icon name="bolt" size={14} className="text-accent" />
                {t("nav.credits", { count: user.credit_balance })}
              </Link>
            )}
            <LanguageSelect />
            <button
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              className="grid h-8 w-8 place-items-center rounded-lg text-muted transition hover:bg-white/[0.06] hover:text-ink"
              aria-label={t("nav.logout")}
              title={t("nav.logout")}
            >
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </header>
      <Announcements />
      <div className="blueprint flex flex-1 flex-col">
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 pb-8 pt-6 sm:px-6 md:pt-8">
          {children ?? <Outlet />}
        </main>
      </div>
      <Footer clearTabBar />
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 flex gap-1 border-t border-accent/25 bg-bg/90 px-2 pb-[max(0.4rem,env(safe-area-inset-bottom))] pt-1.5 backdrop-blur-xl md:hidden"
      >
        {items.map((i) => (
          <NavLink key={i.to} to={i.to} end={i.end} className={tab}>
            <Icon name={i.icon} size={20} />
            <span className="max-w-full truncate">{i.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

export function Footer({ clearTabBar = false }: { clearTabBar?: boolean }) {
  const { t } = useTranslation();
  return (
    <footer className={`border-t border-white/[0.06] pt-5 text-center text-xs text-muted ${clearTabBar ? "pb-24 md:pb-5" : "pb-5"}`}>
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

interface Banner {
  id: string;
  level: "info" | "warning" | "success";
  text_en: string;
  text_uz: string | null;
  text_ru: string | null;
}

function Announcements() {
  const { i18n } = useTranslation();
  const [items, setItems] = useState<Banner[]>([]);
  const [hidden, setHidden] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("aurevid.hiddenBanners") ?? "[]");
    } catch {
      return [];
    }
  });
  useEffect(() => {
    api<Banner[]>("/api/announcements").then(setItems).catch(() => setItems([]));
  }, []);
  const hide = (id: string) => {
    const next = [...hidden, id];
    setHidden(next);
    try {
      localStorage.setItem("aurevid.hiddenBanners", JSON.stringify(next.slice(-50)));
    } catch {
      /* ignore */
    }
  };
  const tone = { info: "border-series-2/40 bg-series-2/10", warning: "border-accent-3/40 bg-accent-3/10", success: "border-ok/40 bg-ok/10" };
  return (
    <>
      {items
        .filter((a) => !hidden.includes(a.id))
        .map((a) => {
          const text = (i18n.language === "uz" && a.text_uz) || (i18n.language === "ru" && a.text_ru) || a.text_en;
          return (
            <div key={a.id} role="status" className={`border-b px-4 py-2 text-sm text-ink ${tone[a.level]}`}>
              <div className="mx-auto flex max-w-7xl items-start justify-between gap-3">
                <p>{a.level === "warning" ? "⚠ " : a.level === "success" ? "✓ " : "ℹ "}{text}</p>
                <button onClick={() => hide(a.id)} aria-label="×" className="text-muted hover:text-ink">✕</button>
              </div>
            </div>
          );
        })}
    </>
  );
}
