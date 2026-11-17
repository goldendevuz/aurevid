// SPDX-License-Identifier: AGPL-3.0-or-later
// Admin panel: overview, users, jobs, analytics, moderation, system, announcements, audit.
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { BarList, ColumnChart, Heatmap, SERIES, StatTile } from "../components/charts";
import { Badge, Button, Card, ErrorText, inputClass } from "../components/ui";

const TABS = ["overview", "users", "jobs", "analytics", "moderation", "system", "announcements", "audit"] as const;
type Tab = (typeof TABS)[number];
type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

function useData<T = Json>(path: string | null, refreshMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const reload = useCallback(async () => {
    if (!path) return;
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, [path]);
  useEffect(() => {
    void reload();
    if (!refreshMs) return;
    const id = setInterval(() => void reload(), refreshMs);
    return () => clearInterval(id);
  }, [reload, refreshMs]);
  return { data, error, reload };
}

function useFmt() {
  const { i18n } = useTranslation();
  const dt = new Intl.DateTimeFormat(i18n.language, { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Tashkent" });
  return {
    date: (v?: string | null) => (v ? dt.format(new Date(v)) : "—"),
    bytes: (n: number) => (n > 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${(n / 1e6).toFixed(1)} MB`),
    secs: (s: number) => (s < 90 ? `${s}s` : s < 5400 ? `${Math.round(s / 60)}m` : `${(s / 3600).toFixed(1)}h`),
  };
}

const qs = (o: Record<string, string | number | boolean | undefined>) =>
  new URLSearchParams(Object.entries(o).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)])).toString();

function Section({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      </div>
      {children}
    </Card>
  );
}

function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: [string, string][]; label: string }) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} className="rounded-md border border-line bg-bg px-2 py-1.5 text-xs text-ink">
      {options.map(([v, l]) => (
        <option key={v} value={v}>{l}</option>
      ))}
    </select>
  );
}

function Status({ s }: { s: string }) {
  const { t } = useTranslation();
  const map: Record<string, ["ok" | "danger" | "paid" | "muted", string]> = {
    healthy: ["ok", "✓"], unhealthy: ["danger", "✕"], warning: ["paid", "!"], disabled: ["muted", "–"],
    done: ["ok", "✓"], failed: ["danger", "✕"], running: ["paid", "▶"], queued: ["muted", "…"],
  };
  const [tone, icon] = map[s] ?? ["muted", "•"];
  return <Badge tone={tone}>{icon} {t(`admin.status_${s}`, { defaultValue: s })}</Badge>;
}

function Pager({ page, total, limit, onPage }: { page: number; total: number; limit: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="mt-3 flex items-center justify-end gap-2 text-xs text-muted">
      <span>{total}</span>
      <Button variant="ghost" className="px-2 py-1" disabled={page <= 1} onClick={() => onPage(page - 1)}>‹</Button>
      <span className="tabular-nums">{page} / {pages}</span>
      <Button variant="ghost" className="px-2 py-1" disabled={page >= pages} onClick={() => onPage(page + 1)}>›</Button>
    </div>
  );
}

const th = "px-2 py-1.5 text-left font-normal text-muted";
const td = "px-2 py-1.5 align-top";

// ---------------------------------------------------------------------------------------------

function Overview({ internal }: { internal: boolean }) {
  const { t } = useTranslation();
  const f = useFmt();
  const [auto, setAuto] = useState(true);
  const { data: s, error } = useData(`/api/admin/stats?include_internal=${internal}`, auto ? 30000 : 0);
  if (!s) return <ErrorText error={error} />;
  const d = (a: number, b: number) => a - b;
  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-xs text-muted">
        <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> {t("admin.autoRefresh")}
      </label>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label={t("admin.usersTotal")} value={s.users.total} hint={`+${s.users.last_24h} / 24h · +${s.users.last_7d} / 7d`} />
        <StatTile label={t("admin.usersToday")} value={s.today.users} delta={d(s.today.users, s.yesterday.users)} hint={t("admin.vsYesterday")} />
        <StatTile label={t("admin.jobsToday")} value={s.today.jobs} delta={d(s.today.jobs, s.yesterday.jobs)} hint={t("admin.vsYesterday")} />
        <StatTile label={t("admin.failedToday")} value={s.today.failed} hint={`${t("admin.failureRate7d")}: ${s.jobs.failure_rate_7d}%`} />
        <StatTile label={t("admin.creditsToday")} value={s.today.credits_spent} delta={d(s.today.credits_spent, s.yesterday.credits_spent)} hint={t("admin.vsYesterday")} />
        <StatTile label={t("admin.queue")} value={`${s.jobs.queued} / ${s.jobs.running}`} hint={`${t("admin.queuedRunning")} · ${t("admin.oldestWait")}: ${f.secs(s.jobs.oldest_queued_seconds)}`} />
        <StatTile label={t("admin.storage")} value={f.bytes(s.storage.bytes)} hint={`${s.storage.assets} ${t("admin.files")}`} />
        <StatTile label={t("admin.safety")} value={`${s.open_reports} / ${s.moderation_7d}`} hint={t("admin.reportsModeration")} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={t("admin.jobsDaily")}>
          <ColumnChart
            series={[{ name: t("admin.succeeded"), color: SERIES[0] }, { name: t("admin.failed"), color: SERIES[1] }]}
            data={s.trends.daily.map((x: Json) => ({ label: x.date.slice(5), values: [x.jobs - x.failed, x.failed] }))}
          />
        </Section>
        <Section title={t("admin.usersDaily")}>
          <ColumnChart series={[{ name: t("admin.newUsers"), color: SERIES[0] }]} data={s.trends.daily.map((x: Json) => ({ label: x.date.slice(5), values: [x.users] }))} />
        </Section>
        <Section title={t("admin.monthly")}>
          <ColumnChart labelEvery={2} series={[{ name: t("admin.jobs"), color: SERIES[0] }]} data={s.trends.monthly.map((x: Json) => ({ label: x.date, values: [x.jobs] }))} />
          <p className="mt-2 text-xs text-muted">
            {t("admin.thisMonth")}: {s.this_month.users} {t("admin.users")} · {s.this_month.jobs} {t("admin.jobs")} — {t("admin.lastMonth")}: {s.last_month.users} · {s.last_month.jobs}
          </p>
        </Section>
        <Section title={t("admin.breakdown")}>
          <BarList rows={Object.entries(s.jobs.by_provider as Record<string, number>).map(([k, v]) => ({ label: k, value: v }))} />
          <p className="mt-3 text-xs text-muted">
            {Object.entries(s.jobs.by_kind as Record<string, number>).map(([k, v]) => `${k}: ${v}`).join(" · ")}
          </p>
        </Section>
        <Section title={t("admin.recentUsers")}>
          <ul className="space-y-1 text-xs">
            {s.recent_users.map((u: Json) => (
              <li key={u.id} className="flex justify-between gap-2"><span className="truncate">{u.email}</span><span className="text-muted">{f.date(u.created_at)}</span></li>
            ))}
          </ul>
        </Section>
        <Section title={t("admin.recentFailures")}>
          <ul className="space-y-2 text-xs">
            {s.recent_failures.length === 0 && <li className="text-muted">—</li>}
            {s.recent_failures.map((j: Json) => (
              <li key={j.id}>
                <span className="text-muted">{f.date(j.created_at)} · {j.provider} · {j.email}</span>
                <p className="text-danger">{j.error}</p>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

function UserDetail({ id, onChanged, onClose }: { id: string; onChanged: () => void; onClose: () => void }) {
  const { t } = useTranslation();
  const f = useFmt();
  const { data, reload } = useData(`/api/admin/users/${id}`);
  const [amount, setAmount] = useState(10);
  const [error, setError] = useState<unknown>(null);
  const act = async (path: string, body: object) => {
    setError(null);
    try {
      await api(`/api/admin/users/${id}/${path}`, { method: "POST", body });
      await reload();
      onChanged();
    } catch (e) {
      setError(e);
    }
  };
  if (!data) return null;
  const u = data.user;
  return (
    <Card className="border-amber/40">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{u.email}</p>
          <p className="text-[11px] text-muted">
            {u.id} · {f.date(u.created_at)} · {t("admin.activeDays")}: {data.active_days} · {t("admin.lastActive")}: {data.last_active ?? "—"}
          </p>
        </div>
        <button onClick={onClose} className="text-muted hover:text-ink">✕</button>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <Badge tone="paid">{u.credit_balance} cr</Badge>
        {u.is_admin && <Badge tone="ok">admin</Badge>}
        {u.is_internal && <Badge tone="muted">{t("admin.internal")}</Badge>}
        {u.is_blocked && <Badge tone="danger">{t("admin.blocked")}</Badge>}
        <Badge tone="muted">{t("admin.keys")}: {data.provider_keys.join(", ") || "—"}</Badge>
        <Badge tone="muted">{f.bytes(data.assets.bytes)} · {data.assets.count} {t("admin.files")}</Badge>
        {Object.entries(data.moderation as Record<string, number>).map(([k, v]) => (
          <Badge key={k} tone="danger">{k}: {v}</Badge>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input type="number" min={1} max={100000} value={amount} onChange={(e) => setAmount(Number(e.target.value))} className={`${inputClass} w-24`} aria-label={t("admin.amount")} />
        <Button className="px-3 py-1.5" onClick={() => void act("credits", { amount, mode: "add", note_id: crypto.randomUUID().slice(0, 12) })}>+ {t("admin.credits")}</Button>
        <Button variant="ghost" className="px-3 py-1.5" onClick={() => void act("credits", { amount, mode: "deduct", note_id: crypto.randomUUID().slice(0, 12) })}>− {t("admin.credits")}</Button>
        <Button variant="danger" className="px-3 py-1.5" onClick={() => confirm(t("admin.confirm")) && void act("block", { blocked: !u.is_blocked })}>
          {u.is_blocked ? t("admin.unblock") : t("admin.block")}
        </Button>
        <Button variant="ghost" className="px-3 py-1.5" onClick={() => void act("internal", { value: !u.is_internal })}>
          {u.is_internal ? t("admin.markCustomer") : t("admin.markInternal")}
        </Button>
        <Button variant="ghost" className="px-3 py-1.5" onClick={() => confirm(t("admin.confirm")) && void act("admin", { value: !u.is_admin })}>
          {u.is_admin ? t("admin.removeAdmin") : t("admin.makeAdmin")}
        </Button>
      </div>
      <ErrorText error={error} />
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-semibold">{t("admin.jobs")}</p>
          <ul className="space-y-1 text-[11px]">
            {data.jobs.map((j: Json) => (
              <li key={j.id} className="flex items-center gap-2"><Status s={j.status} /> <span className="text-muted">{f.date(j.created_at)} · {j.kind} · {j.provider}</span></li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-1 text-xs font-semibold">{t("admin.ledger")}</p>
          <ul className="space-y-1 text-[11px] tabular-nums">
            {data.ledger.map((e: Json, i: number) => (
              <li key={i} className="flex justify-between"><span className="text-muted">{f.date(e.created_at)} · {e.reason}</span><span>{e.delta > 0 ? `+${e.delta}` : e.delta} → {e.balance_after}</span></li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}

function Users() {
  const { t } = useTranslation();
  const f = useFmt();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [activity, setActivity] = useState("all");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const { data, error, reload } = useData(`/api/admin/users?${qs({ q, filter, activity, sort, page, limit: 25 })}`);
  useEffect(() => setPage(1), [q, filter, activity, sort]);
  return (
    <div className="space-y-4">
      {open && <UserDetail id={open} onChanged={() => void reload()} onClose={() => setOpen(null)} />}
      <Section
        title={t("admin.tab_users")}
        actions={
          <>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("admin.search")} className="rounded-md border border-line bg-bg px-2 py-1.5 text-xs" />
            <Select label="filter" value={filter} onChange={setFilter} options={["all", "customers", "internal", "blocked", "admins"].map((v) => [v, t(`admin.f_${v}`)])} />
            <Select label="activity" value={activity} onChange={setActivity} options={["all", "activated", "unactivated", "tried_failed"].map((v) => [v, t(`admin.a_${v}`)])} />
            <Select label="sort" value={sort} onChange={setSort} options={["newest", "oldest", "balance_desc", "balance_asc", "jobs_desc", "last_active"].map((v) => [v, t(`admin.s_${v}`)])} />
            <a className="text-xs text-amber hover:underline" href={`/api/admin/export/users.csv?${qs({ filter, activity })}`} download>⬇ CSV</a>
          </>
        }
      >
        <ErrorText error={error} />
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr><th className={th}>Email</th><th className={th}>{t("admin.created")}</th><th className={th}>{t("admin.credits")}</th><th className={th}>{t("admin.jobs")}</th><th className={th}>{t("admin.lastActive")}</th><th className={th} /></tr></thead>
            <tbody>
              {data?.items.map((u: Json) => (
                <tr key={u.id} className="cursor-pointer border-t border-line hover:bg-raised" onClick={() => setOpen(u.id)}>
                  <td className={td}>{u.email}</td>
                  <td className={`${td} text-muted`}>{f.date(u.created_at)}</td>
                  <td className={`${td} tabular-nums`}>{u.credit_balance}</td>
                  <td className={`${td} tabular-nums`}>{u.done}/{u.jobs}</td>
                  <td className={`${td} text-muted`}>{u.last_active ?? "—"}</td>
                  <td className={`${td} space-x-1`}>
                    {u.is_admin && <Badge tone="ok">admin</Badge>}
                    {u.is_internal && <Badge tone="muted">{t("admin.internal")}</Badge>}
                    {u.is_blocked && <Badge tone="danger">{t("admin.blocked")}</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && <Pager page={page} total={data.total} limit={25} onPage={setPage} />}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

function Jobs({ internal }: { internal: boolean }) {
  const { t } = useTranslation();
  const f = useFmt();
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [range, setRange] = useState("7d");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const { data, reload } = useData(`/api/admin/jobs?${qs({ status, kind, range, q, page, limit: 25, include_internal: internal })}`, 15000);
  const errors = useData<Json[]>(`/api/admin/jobs/errors?days=7`);
  useEffect(() => setPage(1), [status, kind, range, q]);
  const act = async (id: string, action: string) => {
    setError(null);
    try {
      await api(`/api/admin/jobs/${id}/${action}`, { method: "POST" });
      await reload();
    } catch (e) {
      setError(e);
    }
  };
  return (
    <div className="space-y-4">
      <Section
        title={t("admin.tab_jobs")}
        actions={
          <>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("admin.searchJobs")} className="rounded-md border border-line bg-bg px-2 py-1.5 text-xs" />
            <Select label="status" value={status} onChange={setStatus} options={[["", t("admin.f_all")], ...["queued", "running", "done", "failed"].map((v) => [v, t(`admin.status_${v}`)] as [string, string])]} />
            <Select label="kind" value={kind} onChange={setKind} options={[["", t("admin.f_all")], ["image", "image"], ["video", "video"], ["upscale", "upscale"]]} />
            <Select label="range" value={range} onChange={setRange} options={["today", "7d", "30d", "90d", "all"].map((v) => [v, t(`admin.r_${v}`)])} />
            <a className="text-xs text-amber hover:underline" href={`/api/admin/export/jobs.csv?${qs({ range: range === "today" ? "7d" : range, include_internal: internal })}`} download>⬇ CSV</a>
          </>
        }
      >
        <ErrorText error={error} />
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr><th className={th}>{t("admin.created")}</th><th className={th}>{t("admin.user")}</th><th className={th}>{t("admin.type")}</th><th className={th}>Status</th><th className={th}>{t("admin.time")}</th><th className={th}>{t("admin.credits")}</th><th className={th} /></tr></thead>
            <tbody>
              {data?.items.map((j: Json) => (
                <tr key={j.id} className="border-t border-line">
                  <td className={`${td} whitespace-nowrap text-muted`}>{f.date(j.created_at)}</td>
                  <td className={td}>{j.user_email}</td>
                  <td className={td}>{j.kind}{j.upscale ? ` · ${j.upscale.toUpperCase()}` : ""}<p className="text-[10px] text-muted">{j.provider} · {j.model}</p></td>
                  <td className={td}><Status s={j.status} />{j.error && <p className="mt-0.5 max-w-64 text-[10px] text-danger">{j.error}</p>}</td>
                  <td className={`${td} tabular-nums text-muted`}>{j.seconds ?? "—"}s</td>
                  <td className={`${td} tabular-nums`}>{j.cost}</td>
                  <td className={td}>
                    {j.status === "queued" && <Button variant="danger" className="px-2 py-1 text-[11px]" onClick={() => void act(j.id, "cancel")}>{t("admin.cancel")}</Button>}
                    {j.status === "failed" && <Button variant="ghost" className="px-2 py-1 text-[11px]" onClick={() => void act(j.id, "retry")}>{t("admin.retry")}</Button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data && <Pager page={page} total={data.total} limit={25} onPage={setPage} />}
      </Section>
      <Section title={t("admin.topErrors")}>
        {errors.data?.length ? (
          <BarList rows={errors.data.map((e) => ({ label: `${e.provider}: ${e.error}`, value: e.count }))} />
        ) : (
          <p className="text-xs text-muted">—</p>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

function Analytics({ internal }: { internal: boolean }) {
  const { t } = useTranslation();
  const [days, setDays] = useState("30");
  const [gran, setGran] = useState("weekly");
  const [metric, setMetric] = useState("activity");
  const funnel = useData(`/api/admin/funnel?days=${days}&include_internal=${internal}`);
  const ret = useData(`/api/admin/retention?days=14&include_internal=${internal}`);
  const coh = useData(`/api/admin/cohorts?granularity=${gran}&metric=${metric}&periods=8&include_internal=${internal}`);
  const r = ret.data;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section title={t("admin.funnel")} actions={<Select label="days" value={days} onChange={setDays} options={[["7", "7d"], ["30", "30d"], ["90", "90d"], ["0", t("admin.r_all")]]} />}>
        {funnel.data && (
          <>
            <BarList rows={funnel.data.steps.map((s: Json) => ({ label: t(`admin.step_${s.step}`), value: s.users, note: `${s.of_previous}% · ${s.of_total}%` }))} />
            <p className="mt-3 text-[11px] text-muted">{t("admin.funnelNote", { n: funnel.data.tried_but_failed })}</p>
          </>
        )}
      </Section>
      <Section title={t("admin.retention")}>
        {r && (
          <>
            <div className="mb-3 grid grid-cols-3 gap-2">
              <StatTile label={t("admin.activeToday")} value={r.today.active} delta={r.today.active - r.yesterday.active} hint={t("admin.vsYesterday")} />
              <StatTile label={t("admin.returningToday")} value={r.today.returning} hint={`${t("admin.newUsers")}: ${r.today.new}`} />
              <StatTile label={t("admin.returningRate")} value={`${r.returning_rate}%`} hint={`${r.returned_users}/${r.users_total}`} />
            </div>
            <ColumnChart
              labelEvery={3}
              series={[{ name: t("admin.returning"), color: SERIES[0] }, { name: t("admin.newUsers"), color: SERIES[1] }]}
              data={r.series.map((x: Json) => ({ label: x.date.slice(5), values: [x.returning, x.new] }))}
            />
          </>
        )}
      </Section>
      <Section title={t("admin.frequency")}>
        {r && <BarList rows={r.frequency.map((b: Json) => ({ label: t("admin.daysBucket", { b: b.bucket }), value: b.users }))} />}
        {r && (
          <table className="mt-4 w-full text-xs">
            <thead><tr><th className={th}>Email</th><th className={th}>{t("admin.lastActive")}</th><th className={th}>{t("admin.activeDays")}</th><th className={th}>{t("admin.streak")}</th></tr></thead>
            <tbody>
              {r.recent.slice(0, 10).map((u: Json) => (
                <tr key={u.id} className="border-t border-line"><td className={td}>{u.email}</td><td className={`${td} text-muted`}>{u.last_active}</td><td className={`${td} tabular-nums`}>{u.active_days}</td><td className={`${td} tabular-nums`}>{u.streak}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
      <Section
        title={t("admin.cohorts")}
        actions={
          <>
            <Select label="granularity" value={gran} onChange={setGran} options={[["weekly", t("admin.weekly")], ["monthly", t("admin.monthlyG")]]} />
            <Select label="metric" value={metric} onChange={setMetric} options={[["activity", t("admin.m_activity")], ["jobs", t("admin.m_jobs")]]} />
          </>
        }
      >
        {coh.data && (
          <>
            <Heatmap rows={coh.data.rows} columnLabel={(i) => `${gran === "weekly" ? "W" : "M"}${i}`} />
            <p className="mt-3 text-[11px] text-muted">
              {t("admin.ttfj")}: {coh.data.time_to_first_job_hours.median ?? "—"}h ({t("admin.median")}), {coh.data.time_to_first_job_hours.mean ?? "—"}h ({t("admin.mean")})
            </p>
          </>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

function Moderation() {
  const { t } = useTranslation();
  const f = useFmt();
  const mod = useData(`/api/admin/moderation?days=30`);
  const reports = useData<Json[]>(`/api/admin/reports`);
  const [error, setError] = useState<unknown>(null);
  const run = async (path: string, method: "POST" | "DELETE", body?: object) => {
    setError(null);
    try {
      await api(path, { method, body });
      await Promise.all([mod.reload(), reports.reload()]);
    } catch (e) {
      setError(e);
    }
  };
  return (
    <div className="space-y-4">
      <ErrorText error={error} />
      <Section title={t("admin.reports")}>
        {reports.data?.length === 0 && <p className="text-xs text-muted">{t("admin.noReports")}</p>}
        <div className="grid gap-3 md:grid-cols-2">
          {reports.data?.map((r) => (
            <div key={r.id} className="flex gap-3 rounded-lg border border-line p-3">
              {r.asset_url && r.asset_mime?.startsWith("image/") && <img src={r.asset_url} alt="" className="h-24 w-24 rounded object-cover" />}
              {r.asset_url && r.asset_mime?.startsWith("video/") && <video src={r.asset_url} className="h-24 w-24 rounded" muted />}
              <div className="flex-1 text-xs">
                <p className="font-semibold">{t(`report.reason_${r.reason}`)}</p>
                <p className="text-muted">{r.asset_owner_email} · {f.date(r.created_at)}</p>
                {r.details && <p className="mt-1">{r.details}</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  {r.asset_id && <Button variant="danger" className="px-2 py-1 text-[11px]" onClick={() => confirm(t("admin.confirm")) && void run(`/api/admin/assets/${r.asset_id}`, "DELETE")}>{t("admin.removeAsset")}</Button>}
                  {r.asset_owner_id && <Button variant="danger" className="px-2 py-1 text-[11px]" onClick={() => confirm(t("admin.confirm")) && void run(`/api/admin/users/${r.asset_owner_id}/block`, "POST", { blocked: true })}>{t("admin.block")}</Button>}
                  <Button variant="ghost" className="px-2 py-1 text-[11px]" onClick={() => void run(`/api/admin/reports/${r.id}/dismiss`, "POST")}>{t("admin.dismiss")}</Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>
      <Section title={t("admin.rejectedPrompts")}>
        {mod.data && (
          <>
            <BarList rows={Object.entries(mod.data.by_category as Record<string, number>).map(([k, v]) => ({ label: k, value: v }))} />
            <p className="mt-2 text-[11px] text-muted">{t("admin.privacyNote")}</p>
            <table className="mt-3 w-full text-xs">
              <thead><tr><th className={th}>Email</th><th className={th}>{t("admin.events")}</th><th className={th}>minors</th><th className={th}>{t("admin.last")}</th><th className={th} /></tr></thead>
              <tbody>
                {mod.data.users.map((u: Json) => (
                  <tr key={u.user_id} className="border-t border-line">
                    <td className={td}>{u.email}</td>
                    <td className={`${td} tabular-nums`}>{u.events}</td>
                    <td className={`${td} tabular-nums ${u.minors_events ? "font-semibold text-danger" : ""}`}>{u.minors_events}</td>
                    <td className={`${td} text-muted`}>{f.date(u.last_at)}</td>
                    <td className={td}>{u.blocked ? <Badge tone="danger">{t("admin.blocked")}</Badge> : <Button variant="danger" className="px-2 py-1 text-[11px]" onClick={() => confirm(t("admin.confirm")) && void run(`/api/admin/users/${u.user_id}/block`, "POST", { blocked: true })}>{t("admin.block")}</Button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

function System() {
  const { t } = useTranslation();
  const f = useFmt();
  const health = useData(`/api/admin/health`, 20000);
  const prov = useData(`/api/admin/providers`, 20000);
  const reset = async (p: string, s: string) => {
    await api(`/api/admin/providers/${p}/${s}/reset`, { method: "POST" });
    await prov.reload();
  };
  const h = health.data;
  return (
    <div className="space-y-4">
      {h && (
        <Section title={t("admin.health")} actions={<><Status s={h.status} /><span className="text-[11px] text-muted">{f.date(h.checked_at)}</span></>}>
          <div className="grid gap-3 md:grid-cols-3">
            {Object.entries(h.checks as Record<string, Json>).map(([name, c]) => (
              <div key={name} className="rounded-lg border border-line p-3 text-xs">
                <div className="mb-1 flex items-center justify-between"><span className="font-semibold">{t(`admin.check_${name}`, { defaultValue: name })}</span><Status s={c.status} /></div>
                {name === "providers" ? (
                  <ul className="space-y-0.5 text-muted">
                    {c.items.map((p: Json) => (
                      <li key={p.id}>{p.id}: {p.server_key ? t("admin.serverKey") : p.needs_user_key ? t("admin.userKeys") : t("admin.noKey")}{p.cooldown ? ` · ${t("admin.cooldown")}` : ""}</li>
                    ))}
                  </ul>
                ) : name === "config" ? (
                  <ul className="space-y-0.5 text-muted">{(c.warnings as string[]).map((w) => <li key={w}>⚠ {w}</li>)}{c.warnings.length === 0 && <li>✓</li>}</ul>
                ) : (
                  <p className="text-muted">
                    {Object.entries(c).filter(([k]) => !["status", "workers"].includes(k)).map(([k, v]) => `${k}: ${v ?? "—"}`).join(" · ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
      <Section title={t("admin.providerLimits")}>
        <p className="mb-2 text-[11px] text-muted">{t("admin.limitsNote", { n: prov.data?.user_scopes ?? 0 })}</p>
        <table className="w-full text-xs">
          <thead><tr><th className={th}>Provider</th><th className={th}>Scope</th><th className={th}>{t("admin.usedToday")}</th><th className={th}>{t("admin.estimate")}</th><th className={th}>{t("admin.cooldown")}</th><th className={th} /></tr></thead>
          <tbody>
            {prov.data?.shared.map((p: Json) => (
              <tr key={p.provider + p.scope} className="border-t border-line">
                <td className={td}>{p.provider}</td>
                <td className={`${td} text-muted`}>{p.scope}</td>
                <td className={`${td} tabular-nums`}>{p.used_today}</td>
                <td className={`${td} tabular-nums`}>{p.estimated_limit ?? "?"} <span className="text-muted">({p.source}, n={p.observations})</span></td>
                <td className={`${td} tabular-nums`}>{p.blocked_seconds ? f.secs(p.blocked_seconds) : "—"}</td>
                <td className={td}>{p.blocked_seconds > 0 && <Button variant="ghost" className="px-2 py-1 text-[11px]" onClick={() => void reset(p.provider, p.scope)}>{t("admin.resetCooldown")}</Button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

function Announcements() {
  const { t } = useTranslation();
  const f = useFmt();
  const list = useData<Json[]>(`/api/admin/announcements`);
  const [form, setForm] = useState({ level: "info", text_en: "", text_uz: "", text_ru: "", ends_at: "" });
  const [error, setError] = useState<unknown>(null);
  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api(`/api/admin/announcements`, {
        method: "POST",
        body: { ...form, text_uz: form.text_uz || null, text_ru: form.text_ru || null, ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null },
      });
      setForm({ level: "info", text_en: "", text_uz: "", text_ru: "", ends_at: "" });
      await list.reload();
    } catch (err) {
      setError(err);
    }
  };
  const run = async (path: string, method: "PATCH" | "DELETE", body?: object) => {
    await api(path, { method, body });
    await list.reload();
  };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section title={t("admin.newAnnouncement")}>
        <form onSubmit={create} className="space-y-2">
          <Select label="level" value={form.level} onChange={(v) => setForm({ ...form, level: v })} options={[["info", "info"], ["warning", "warning"], ["success", "success"]]} />
          {(["text_en", "text_uz", "text_ru"] as const).map((k) => (
            <textarea key={k} required={k === "text_en"} maxLength={500} rows={2} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} placeholder={k.slice(5).toUpperCase()} className={inputClass} />
          ))}
          <label className="block text-[11px] text-muted">
            {t("admin.endsAt")}
            <input type="datetime-local" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} className={`${inputClass} mt-1`} />
          </label>
          <Button type="submit">{t("admin.publish")}</Button>
          <ErrorText error={error} />
        </form>
      </Section>
      <Section title={t("admin.tab_announcements")}>
        <ul className="space-y-2 text-xs">
          {list.data?.map((a) => (
            <li key={a.id} className="rounded-lg border border-line p-3">
              <div className="flex items-center justify-between gap-2">
                <Badge tone={a.active ? "ok" : "muted"}>{a.active ? t("admin.active") : t("admin.inactive")} · {a.level}</Badge>
                <span className="text-muted">{f.date(a.created_at)}{a.ends_at ? ` → ${f.date(a.ends_at)}` : ""}</span>
              </div>
              <p className="mt-1">{a.text_en}</p>
              {a.text_uz && <p className="text-muted">{a.text_uz}</p>}
              <div className="mt-2 flex gap-2">
                <Button variant="ghost" className="px-2 py-1 text-[11px]" onClick={() => void run(`/api/admin/announcements/${a.id}`, "PATCH", { active: !a.active })}>{a.active ? t("admin.deactivate") : t("admin.activate")}</Button>
                <Button variant="danger" className="px-2 py-1 text-[11px]" onClick={() => confirm(t("admin.confirm")) && void run(`/api/admin/announcements/${a.id}`, "DELETE")}>{t("job.delete")}</Button>
              </div>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

function Audit() {
  const { t } = useTranslation();
  const f = useFmt();
  const { data } = useData<Json[]>(`/api/admin/audit?limit=200`);
  return (
    <Section title={t("admin.tab_audit")}>
      <table className="w-full text-xs">
        <thead><tr><th className={th}>{t("admin.created")}</th><th className={th}>Admin</th><th className={th}>{t("admin.action")}</th><th className={th}>{t("admin.target")}</th><th className={th}>{t("admin.details")}</th></tr></thead>
        <tbody>
          {data?.map((a) => (
            <tr key={a.id} className="border-t border-line">
              <td className={`${td} whitespace-nowrap text-muted`}>{f.date(a.created_at)}</td>
              <td className={td}>{a.admin_email}</td>
              <td className={td}><code>{a.action}</code></td>
              <td className={`${td} text-muted`}>{a.target ?? "—"}</td>
              <td className={`${td} text-muted`}>{JSON.stringify(a.details)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

// ---------------------------------------------------------------------------------------------

export default function Admin() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.includes(params.get("tab") as Tab) ? params.get("tab") : "overview") as Tab;
  const [internal, setInternal] = useState(false);
  if (!user?.is_admin) return <Navigate to="/" replace />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{t("admin.title")}</h1>
        <label className="flex items-center gap-2 text-xs text-muted" title={t("admin.internalHint")}>
          <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> {t("admin.includeInternal")}
        </label>
      </div>
      <nav className="flex flex-wrap gap-1 border-b border-line pb-2" role="tablist">
        {TABS.map((k) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
            onClick={() => setParams({ tab: k })}
            className={`rounded-md px-3 py-1.5 text-sm ${tab === k ? "bg-amber text-amber-ink font-semibold" : "text-muted hover:text-ink"}`}
          >
            {t(`admin.tab_${k}`)}
          </button>
        ))}
      </nav>
      {tab === "overview" && <Overview internal={internal} />}
      {tab === "users" && <Users />}
      {tab === "jobs" && <Jobs internal={internal} />}
      {tab === "analytics" && <Analytics internal={internal} />}
      {tab === "moderation" && <Moderation />}
      {tab === "system" && <System />}
      {tab === "announcements" && <Announcements />}
      {tab === "audit" && <Audit />}
    </div>
  );
}
