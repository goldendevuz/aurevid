// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../api";

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}) {
  const styles = {
    primary: "btn-aurora font-semibold",
    ghost: "border border-line bg-raised/40 text-ink hover:border-white/20 hover:bg-raised",
    danger: "border border-danger/50 text-danger hover:bg-danger/10",
  }[variant];
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm", lg: "px-6 py-3 text-base" }[size];
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl transition disabled:cursor-not-allowed disabled:opacity-45 ${sizes} ${styles} ${className}`}
      {...props}
    />
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`glass rounded-[var(--radius-card)] p-5 ${className}`}>{children}</section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function EmptyState({ icon, title, hint }: { icon?: ReactNode; title: ReactNode; hint?: ReactNode }) {
  return (
    <div className="glass flex flex-col items-center gap-2 rounded-[var(--radius-card)] px-6 py-14 text-center">
      {icon && <div className="mb-1 grid h-12 w-12 place-items-center rounded-2xl bg-raised text-accent">{icon}</div>}
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && <p className="max-w-sm text-xs text-muted">{hint}</p>}
    </div>
  );
}

/** Pill-style segmented control (radio semantics via aria-pressed buttons). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className = "",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode }[];
  label?: string;
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={`inline-flex rounded-xl border border-line bg-bg/60 p-1 ${className}`}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
            value === o.value ? "bg-raised text-ink shadow-[inset_0_0_0_1px_rgb(255_255_255/0.08)]" : "text-muted hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-[11px] font-medium uppercase tracking-[0.08em] text-muted">
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-xl border border-white/[0.14] bg-white/[0.05] px-3.5 py-2.5 text-sm text-ink shadow-[inset_0_1px_2px_rgb(0_0_0/0.35)] placeholder:text-muted/60 transition hover:border-white/25 focus:border-accent focus:bg-white/[0.07] focus:outline-none focus:ring-2 focus:ring-accent/30";

export function Badge({ tone, children }: { tone: "free" | "paid" | "muted" | "ok" | "danger"; children: ReactNode }) {
  const styles = {
    free: "bg-ok/12 text-ok",
    paid: "bg-accent-2/15 text-accent-2",
    muted: "bg-raised text-muted",
    ok: "bg-ok/12 text-ok",
    danger: "bg-danger/12 text-danger",
  }[tone];
  return <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ${styles}`}>{children}</span>;
}

export function ErrorText({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  const code = error instanceof ApiError ? error.code : "generic";
  const retry = error instanceof ApiError ? Number(error.detail.retry_after ?? 0) : 0;
  return (
    <p role="alert" className="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
      {t(`errors.${code}`, {
        ...(error instanceof ApiError ? error.detail : {}),
        defaultValue: t("errors.generic"),
        minutes: Math.max(1, Math.ceil(retry / 60)),
      })}
    </p>
  );
}
