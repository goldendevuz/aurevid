// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../api";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" }) {
  const styles = {
    primary: "bg-amber text-amber-ink hover:brightness-110 font-semibold",
    ghost: "border border-line text-ink hover:bg-raised",
    danger: "border border-danger/60 text-danger hover:bg-danger/10",
  }[variant];
  return (
    <button
      className={`rounded-lg px-4 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-[var(--radius-card)] border border-line bg-surface p-5 ${className}`}>
      {children}
    </section>
  );
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-line bg-bg px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-amber focus:outline-none";

export function Badge({ tone, children }: { tone: "free" | "paid" | "muted" | "ok" | "danger"; children: ReactNode }) {
  const styles = {
    free: "bg-ok/15 text-ok",
    paid: "bg-amber/15 text-amber",
    muted: "bg-raised text-muted",
    ok: "bg-ok/15 text-ok",
    danger: "bg-danger/15 text-danger",
  }[tone];
  return <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${styles}`}>{children}</span>;
}

export function ErrorText({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  const code = error instanceof ApiError ? error.code : "generic";
  return (
    <p role="alert" className="mt-3 text-sm text-danger">
      {t(`errors.${code}`, { defaultValue: t("errors.generic") })}
    </p>
  );
}
