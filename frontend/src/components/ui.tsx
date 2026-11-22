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
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}) {
  const styles = {
    primary:
      "bg-accent text-accent-ink font-semibold shadow-[inset_0_-2px_0_rgba(0,0,0,0.28)] hover:opacity-95 active:translate-y-[1px] active:shadow-none",
    secondary:
      "border border-border bg-surface-2 text-text font-medium hover:bg-surface-3 hover:border-border-strong",
    ghost:
      "bg-transparent text-text-2 font-medium hover:bg-surface-2 hover:text-text",
    danger:
      "border border-danger/40 text-danger bg-danger/10 hover:bg-danger/20",
  }[variant];
  const sizes = { sm: "px-3 py-1.5 text-xs rounded-lg", md: "px-4 py-2 text-sm rounded-xl", lg: "px-6 py-2.5 text-base rounded-xl" }[size];
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 transition disabled:cursor-not-allowed disabled:opacity-50 ${sizes} ${styles} ${className}`}
      {...props}
    />
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-border bg-surface-1 p-5 shadow-sm ${className}`}>{children}</section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-text sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-text-2">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function EmptyState({ icon, title, hint }: { icon?: ReactNode; title: ReactNode; hint?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-border bg-surface-1 px-6 py-14 text-center">
      {icon && <div className="mb-1 grid h-12 w-12 place-items-center rounded-2xl bg-surface-2 text-accent">{icon}</div>}
      <p className="text-sm font-semibold text-text">{title}</p>
      {hint && <p className="max-w-sm text-xs text-text-2">{hint}</p>}
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
    <div role="group" aria-label={label} className={`inline-flex rounded-xl border border-border bg-surface-2 p-1 ${className}`}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
            value === o.value ? "bg-surface-3 text-text shadow-sm" : "text-text-2 hover:text-text"
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
    <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium text-text-2">
      {children}
    </label>
  );
}

export const inputClass =
  "w-full rounded-xl border border-border bg-surface-2 px-3.5 py-2.5 text-sm text-text placeholder:text-text-3/60 transition hover:border-border-strong focus:border-accent focus:bg-surface-3 focus:outline-none focus:ring-1 focus:ring-accent";

export function Badge({ tone, children }: { tone: "free" | "paid" | "muted" | "ok" | "danger" | "live"; children: ReactNode }) {
  const styles = {
    free: "bg-success/15 text-success",
    paid: "bg-surface-2 border border-border text-text-2",
    muted: "bg-surface-2 text-text-3",
    ok: "bg-success/15 text-success",
    danger: "bg-danger/15 text-danger",
    live: "bg-accent/15 text-accent font-mono",
  }[tone];
  return <span className={`inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-medium ${styles}`}>{children}</span>;
}

export function ErrorText({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  const code = error instanceof ApiError ? error.code : "generic";
  const retry = error instanceof ApiError ? Number(error.detail.retry_after ?? 0) : 0;
  return (
    <p role="alert" className="mt-3 rounded-xl border border-danger/30 bg-danger/10 px-3.5 py-2.5 text-sm text-danger">
      {t(`errors.${code}`, {
        ...(error instanceof ApiError ? error.detail : {}),
        defaultValue: t("errors.generic"),
        minutes: Math.max(1, Math.ceil(retry / 60)),
      })}
    </p>
  );
}
