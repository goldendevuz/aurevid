// SPDX-License-Identifier: AGPL-3.0-or-later
// Small dependency-free charts for the admin panel (HTML/CSS, dark theme).
// Rules: thin marks, 4px rounded data ends, 2px surface gaps, hover tooltips, legend for 2+
// series, recessive grid, text in ink colors (never the series color), sequential = one hue.
import { useState, type ReactNode } from "react";

export const SERIES = ["var(--color-series-1)", "var(--color-series-2)"];

export function StatTile({ label, value, delta, hint }: { label: string; value: ReactNode; delta?: number | null; hint?: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-ink">{value}</p>
      {delta !== undefined && delta !== null && (
        <p className={`mt-0.5 text-[11px] tabular-nums ${delta > 0 ? "text-ok" : delta < 0 ? "text-danger" : "text-muted"}`}>
          {delta > 0 ? "▲" : delta < 0 ? "▼" : "•"} {Math.abs(delta)} {hint}
        </p>
      )}
      {delta === undefined && hint && <p className="mt-0.5 text-[11px] text-muted">{hint}</p>}
    </div>
  );
}

export function Legend({ items }: { items: { name: string; color: string }[] }) {
  return (
    <div className="mb-2 flex flex-wrap gap-3 text-[11px] text-muted">
      {items.map((s) => (
        <span key={s.name} className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
          {s.name}
        </span>
      ))}
    </div>
  );
}

/** Columns over time; one or two stacked series. */
export function ColumnChart({
  data,
  series,
  height = 160,
  labelEvery = 5,
}: {
  data: { label: string; values: number[] }[];
  series: { name: string; color: string }[];
  height?: number;
  labelEvery?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const totals = data.map((d) => d.values.reduce((a, b) => a + b, 0));
  const max = Math.max(1, ...totals);
  const ticks = [max, Math.round(max / 2), 0];
  return (
    <div>
      {series.length > 1 && <Legend items={series} />}
      <div className="relative flex gap-2">
        <div className="flex flex-col justify-between text-right text-[10px] tabular-nums text-muted" style={{ height }}>
          {ticks.map((t) => (
            <span key={t}>{t}</span>
          ))}
        </div>
        <div className="relative flex-1">
          {ticks.map((_, i) => (
            <div key={i} className="absolute inset-x-0 border-t border-line/50" style={{ top: `${(i / 2) * 100}%` }} />
          ))}
          <div className="relative flex items-end gap-[2px]" style={{ height }} onMouseLeave={() => setHover(null)}>
            {data.map((d, i) => (
              <div
                key={d.label}
                className="flex h-full flex-1 cursor-default flex-col justify-end items-center"
                onMouseEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                tabIndex={0}
                aria-label={`${d.label}: ${series.map((s, k) => `${s.name} ${d.values[k] ?? 0}`).join(", ")}`}
              >
                <div className="flex w-full max-w-6 flex-col-reverse gap-[2px]">
                  {d.values.map((v, k) =>
                    v > 0 ? (
                      <div
                        key={k}
                        style={{
                          height: `${(v / max) * height}px`,
                          background: series[k]?.color,
                          opacity: hover === null || hover === i ? 1 : 0.45,
                        }}
                        className={k === d.values.length - 1 || d.values.slice(k + 1).every((x) => x === 0) ? "rounded-t" : ""}
                      />
                    ) : null,
                  )}
                </div>
              </div>
            ))}
          </div>
          {hover !== null && (
            <div
              className="pointer-events-none absolute -top-2 z-10 -translate-x-1/2 -translate-y-full rounded-md border border-line bg-raised px-2 py-1 text-[11px] text-ink shadow-lg"
              style={{ left: `${((hover + 0.5) / data.length) * 100}%` }}
            >
              <p className="font-semibold">{data[hover].label}</p>
              {series.map((s, k) => (
                <p key={s.name} className="tabular-nums">
                  <span className="mr-1 inline-block h-2 w-2 rounded-sm" style={{ background: s.color }} />
                  {s.name}: {data[hover].values[k] ?? 0}
                </p>
              ))}
            </div>
          )}
          <div className="relative mt-1 h-3 text-[10px] text-muted">
            {data.map((d, i) =>
              i % labelEvery === 0 || i === data.length - 1 ? (
                <span
                  key={d.label}
                  className="absolute -translate-x-1/2 whitespace-nowrap"
                  style={{ left: `${((i + 0.5) / data.length) * 100}%` }}
                >
                  {d.label}
                </span>
              ) : null,
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Horizontal bars with value at the tip (funnels, distributions). Single series. */
export function BarList({ rows, unit = "" }: { rows: { label: string; value: number; note?: string }[]; unit?: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[minmax(110px,30%)_1fr] items-center gap-3 text-xs" title={`${r.label}: ${r.value}${unit}`}>
          <span className="truncate text-muted">{r.label}</span>
          <div className="flex items-center gap-2">
            <div className="h-3.5 rounded-r" style={{ width: `${(r.value / max) * 85}%`, minWidth: r.value ? 3 : 0, background: SERIES[0] }} />
            <span className="whitespace-nowrap tabular-nums text-ink">
              {r.value}
              {unit}
              {r.note && <span className="ml-1.5 text-muted">{r.note}</span>}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Cohort heatmap: one hue, more = stronger; the % is printed so color is never the only cue. */
export function Heatmap({ rows, columnLabel }: { rows: { cohort: string; size: number; values: (number | null)[] }[]; columnLabel: (i: number) => string }) {
  const cols = rows[0]?.values.length ?? 0;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-[2px] text-[11px] tabular-nums">
        <thead>
          <tr className="text-muted">
            <th className="px-2 text-left font-normal">Cohort</th>
            <th className="px-2 text-right font-normal">n</th>
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i} className="px-1 font-normal">{columnLabel(i)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.cohort}>
              <td className="whitespace-nowrap px-2 text-muted">{r.cohort}</td>
              <td className="px-2 text-right text-muted">{r.size}</td>
              {r.values.map((v, i) => {
                const strength = v === null ? 0 : 0.1 + (v / 100) * 0.85;
                return (
                  <td
                    key={i}
                    title={v === null ? "" : `${r.cohort} · ${columnLabel(i)}: ${v}%`}
                    className={`h-7 min-w-11 rounded text-center ${strength > 0.55 ? "text-amber-ink" : "text-ink"}`}
                    style={{ background: v === null ? "transparent" : `rgba(201,133,0,${strength.toFixed(2)})` }}
                  >
                    {v === null ? "" : `${Math.round(v)}%`}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
