// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { LANGUAGES } from "../i18n";
import type { Locale, User } from "../types";
import { Icon } from "./icons";

const SOURCE_URL = import.meta.env.VITE_SOURCE_URL as string | undefined;

export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="8" fill="#09090b" />
      <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" stroke="rgba(255,255,255,0.12)" />
      <path d="M16 6.5 7.5 25.5h4.2l1.8-4.4h5l1.8 4.4h4.2L16 6.5Zm0 6.8 1.8 4.5h-3.6l1.8-4.5Z" fill="#c8ff2e" />
      <circle cx="24.5" cy="8" r="2.2" fill="#c8ff2e" />
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
      className="flex items-center gap-2.5 text-base font-semibold tracking-[-0.02em] text-text"
    >
      <LogoMark />
      <span className="font-semibold text-lg tracking-[-0.02em] text-text">aurevid</span>
    </Link>
  );
}

export function LanguageSelect({ className = "" }: { className?: string }) {
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
      className={`rounded-lg border border-border bg-surface-2 px-2 py-1 text-xs text-text-2 transition hover:border-border-strong hover:text-text focus:border-accent focus:outline-none ${className}`}
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  );
}

export default function Layout({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [scrolled, setScrolled] = useState(false);
  const [avatarOpen, setAvatarOpen] = useState(false);
  const avatarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (avatarRef.current && !avatarRef.current.contains(e.target as Node)) {
        setAvatarOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const isMarketing = pathname === "/" || pathname === "/terms";
  const headerHeight = isMarketing && !scrolled ? "h-14" : "h-11";

  // Desktop links: Explore / Create / Library / Pricing
  const navLinks = [
    { to: "/", label: t("nav.explore", { defaultValue: "Explore" }), end: true },
    { to: "/create", label: t("nav.studio", { defaultValue: "Create" }) },
    { to: "/library", label: t("nav.library", { defaultValue: "Library" }) },
    { to: "/credits", label: t("nav.pricing", { defaultValue: "Pricing" }) },
  ];

  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <header
        className={`sticky top-0 z-40 w-full border-b border-border bg-bg/85 backdrop-blur-md transition-all duration-200 ${headerHeight}`}
      >
        <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-4 sm:px-6">
          {/* Left: Logo */}
          <div className="flex items-center gap-6">
            <Logo />
          </div>

          {/* Centre: Desktop Links */}
          <nav aria-label="Main" className="hidden items-center gap-6 md:flex">
            {navLinks.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `text-sm transition-colors duration-150 py-1 ${
                    isActive
                      ? "text-accent font-semibold relative after:absolute after:-bottom-2.5 after:left-1/2 after:-translate-x-1/2 after:w-4 after:h-[2px] after:bg-accent after:rounded-full"
                      : "text-text-2 hover:text-text font-medium"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Right: Credits / Auth controls */}
          <div className="flex items-center gap-2 sm:gap-3">
            {user ? (
              <>
                <Link
                  to="/credits"
                  className="flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-3 py-1 font-mono text-xs font-semibold text-text transition hover:border-border-strong hover:bg-surface-3"
                  title={t("nav.credits", { count: user.credit_balance })}
                >
                  <Icon name="bolt" size={13} className="text-accent" />
                  <span className="tabular-nums">{user.credit_balance}</span>
                </Link>

                <Link
                  to="/credits"
                  className="hidden rounded-lg border border-border bg-surface-2 px-3 py-1 text-xs font-medium text-text transition hover:bg-surface-3 sm:inline-flex"
                >
                  {t("nav.upgrade", { defaultValue: "Upgrade" })}
                </Link>

                <LanguageSelect className="hidden sm:inline-block" />

                {/* Avatar menu */}
                <div ref={avatarRef} className="relative">
                  <button
                    type="button"
                    onClick={() => setAvatarOpen((v) => !v)}
                    aria-expanded={avatarOpen}
                    aria-label="User menu"
                    className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface-2 text-xs font-semibold text-text transition hover:bg-surface-3 hover:border-border-strong"
                  >
                    {user.email ? user.email.slice(0, 2).toUpperCase() : <Icon name="settings" size={15} />}
                  </button>

                  {avatarOpen && (
                    <div className="absolute right-0 top-full mt-2 w-48 rounded-xl border border-border bg-surface-1 p-1.5 shadow-xl backdrop-blur-xl">
                      <div className="border-b border-border px-2.5 py-1.5 text-xs text-text-3 truncate">
                        {user.email}
                      </div>
                      <Link
                        to="/credits"
                        onClick={() => setAvatarOpen(false)}
                        className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-2 hover:bg-surface-2 hover:text-text transition"
                      >
                        <Icon name="coins" size={14} />
                        {t("nav.usage", { defaultValue: "Usage & Credits" })}
                      </Link>
                      <Link
                        to="/settings"
                        onClick={() => setAvatarOpen(false)}
                        className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-2 hover:bg-surface-2 hover:text-text transition"
                      >
                        <Icon name="settings" size={14} />
                        {t("nav.settings", { defaultValue: "Settings" })}
                      </Link>
                      <Link
                        to="/settings"
                        onClick={() => setAvatarOpen(false)}
                        className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-2 hover:bg-surface-2 hover:text-text transition"
                      >
                        <Icon name="key" size={14} />
                        {t("settings.keys", { defaultValue: "Keys" })}
                      </Link>
                      {user.is_admin && (
                        <Link
                          to="/admin"
                          onClick={() => setAvatarOpen(false)}
                          className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-2 hover:bg-surface-2 hover:text-text transition"
                        >
                          <Icon name="shield" size={14} />
                          {t("nav.admin", { defaultValue: "Admin" })}
                        </Link>
                      )}
                      <div className="my-1 border-t border-border" />
                      <button
                        type="button"
                        onClick={async () => {
                          setAvatarOpen(false);
                          await logout();
                          navigate("/login");
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-danger hover:bg-danger/10 transition"
                      >
                        <Icon name="logout" size={14} />
                        {t("nav.logout", { defaultValue: "Sign out" })}
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <LanguageSelect />
                <Link
                  to="/login"
                  className="rounded-lg px-3 py-1.5 text-xs font-medium text-text-2 transition hover:bg-surface-2 hover:text-text"
                >
                  {t("nav.login", { defaultValue: "Log in" })}
                </Link>
                <Link
                  to="/register"
                  className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-accent-ink shadow-[inset_0_-2px_0_rgba(0,0,0,0.25)] transition hover:opacity-95"
                >
                  {t("nav.signup", { defaultValue: "Sign up" })}
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <Announcements />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 pb-20 pt-4 sm:px-6 md:pb-8 md:pt-6">
        {children ?? <Outlet />}
      </main>

      <Footer clearTabBar />

      {/* Mobile Fixed Bottom Tab Bar (<1024px) */}
      <nav
        aria-label="Mobile Navigation"
        className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-around border-t border-border bg-bg/95 px-2 pb-[max(0.6rem,env(safe-area-inset-bottom))] pt-1 backdrop-blur-xl md:hidden overflow-x-hidden"
      >
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `flex min-w-0 flex-1 flex-col items-center gap-0.5 py-1 text-[11px] font-medium transition ${
              isActive ? "text-accent" : "text-text-3 hover:text-text"
            }`
          }
        >
          <Icon name="search" size={18} />
          <span>{t("nav.explore", { defaultValue: "Explore" })}</span>
        </NavLink>

        {/* Center Create Button: accent, larger, raised */}
        <NavLink
          to="/create"
          className={({ isActive }) =>
            `-mt-3 flex h-11 w-12 flex-col items-center justify-center rounded-xl bg-accent text-accent-ink shadow-[inset_0_-2px_0_rgba(0,0,0,0.28)] transition hover:opacity-95 active:translate-y-[1px] ${
              isActive ? "ring-2 ring-accent ring-offset-2 ring-offset-bg" : ""
            }`
          }
        >
          <Icon name="sparkle" size={20} />
          <span className="text-[10px] font-bold leading-none mt-0.5">
            {t("nav.studio", { defaultValue: "Create" })}
          </span>
        </NavLink>

        <NavLink
          to="/library"
          className={({ isActive }) =>
            `flex min-w-0 flex-1 flex-col items-center gap-0.5 py-1 text-[11px] font-medium transition ${
              isActive ? "text-accent" : "text-text-3 hover:text-text"
            }`
          }
        >
          <Icon name="history" size={18} />
          <span>{t("nav.library", { defaultValue: "Library" })}</span>
        </NavLink>

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex min-w-0 flex-1 flex-col items-center gap-0.5 py-1 text-[11px] font-medium transition ${
              isActive ? "text-accent" : "text-text-3 hover:text-text"
            }`
          }
        >
          <Icon name="settings" size={18} />
          <span>{t("nav.account", { defaultValue: "Account" })}</span>
        </NavLink>
      </nav>
    </div>
  );
}

export function Footer({ clearTabBar = false }: { clearTabBar?: boolean }) {
  const { t } = useTranslation();
  return (
    <footer
      className={`border-t border-border bg-surface-1/40 py-8 text-xs text-text-3 ${
        clearTabBar ? "pb-24 md:pb-8" : "pb-8"
      }`}
    >
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <Link to="/" className="hover:text-text transition">
            {t("nav.explore", { defaultValue: "Explore" })}
          </Link>
          <Link to="/create" className="hover:text-text transition">
            {t("nav.studio", { defaultValue: "Create" })}
          </Link>
          <Link to="/library" className="hover:text-text transition">
            {t("nav.library", { defaultValue: "Library" })}
          </Link>
          <Link to="/credits" className="hover:text-text transition">
            {t("nav.pricing", { defaultValue: "Pricing" })}
          </Link>
          <Link to="/terms" className="hover:text-text transition">
            {t("nav.terms", { defaultValue: "Terms" })}
          </Link>
          <Link to="/terms" className="hover:text-text transition">
            {t("nav.privacy", { defaultValue: "Privacy" })}
          </Link>
          {SOURCE_URL ? (
            <a href={SOURCE_URL} rel="noopener noreferrer" target="_blank" className="hover:text-text transition">
              GitHub ↗
            </a>
          ) : (
            <span>AGPL-3.0</span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span>License AGPL-3.0</span>
          <span>·</span>
          <LanguageSelect />
        </div>
      </div>
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

  const tone = {
    info: "border-info/40 bg-info/10 text-text",
    warning: "border-warning/40 bg-warning/10 text-text",
    success: "border-success/40 bg-success/10 text-text",
  };

  return (
    <>
      {items
        .filter((a) => !hidden.includes(a.id))
        .map((a) => {
          const text = (i18n.language === "uz" && a.text_uz) || (i18n.language === "ru" && a.text_ru) || a.text_en;
          return (
            <div key={a.id} role="status" className={`border-b px-4 py-2 text-sm ${tone[a.level]}`}>
              <div className="mx-auto flex max-w-7xl items-start justify-between gap-3">
                <p>
                  {a.level === "warning" ? "⚠ " : a.level === "success" ? "✓ " : "ℹ "}
                  {text}
                </p>
                <button onClick={() => hide(a.id)} aria-label="×" className="text-text-3 hover:text-text">
                  ✕
                </button>
              </div>
            </div>
          );
        })}
    </>
  );
}
