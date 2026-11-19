// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { useAuth } from "../auth";
import { BuyCredits } from "../components/BuyCredits";
import { Card, ErrorText, PageHeader } from "../components/ui";
import type { Provider, Usage } from "../types";
import { QuotaLine } from "./Studio";

export default function UsagePage() {
  const { t, i18n } = useTranslation();
  const [usage, setUsage] = useState<Usage | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [error, setError] = useState<unknown>(null);
  const { reload } = useAuth();
  const loadUsage = () => api<Usage>("/api/credits").then(setUsage).catch(setError);

  useEffect(() => {
    void loadUsage();
    api<Provider[]>("/api/providers")
      .then((p) => setProviders(p.filter((x) => x.quota && x.available)))
      .catch(setError);
  }, []);

  const pct = usage ? Math.min(100, (usage.jobs_today / usage.daily_job_limit) * 100) : 0;
  const fmt = new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" });

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageHeader title={t("usage.title")} />
      <ErrorText error={error} />
      {usage && (
        <>
          <Card>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-muted">{t("usage.balance")}</p>
            <p className="aurora-text mt-1 text-6xl font-semibold tabular-nums tracking-tight">{usage.balance}</p>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-raised">
              <div className="h-full rounded-full" style={{ width: `${pct}%`, background: "var(--aurora)" }} />
            </div>
            <p className="mt-2 text-xs text-muted">
              {t("usage.today", { used: usage.jobs_today, limit: usage.daily_job_limit })}
            </p>
            <p className="mt-3 text-xs text-muted">{t("usage.note")}</p>
          </Card>
          <BuyCredits
            onPaid={() => {
              void loadUsage();
              void reload();
            }}
          />
          {providers.length > 0 && (
            <Card>
              <h2 className="text-sm font-semibold">{t("usage.limits")}</h2>
              <p className="mb-3 mt-1 text-xs text-muted">{t("usage.limitsHelp")}</p>
              <ul className="divide-y divide-line">
                {providers.map((p) => (
                  <li key={p.id} className="py-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span>{p.name}</span>
                      <span className="text-xs text-muted">
                        {t("usage.usedToday")}: {p.quota!.used_today} · {t("usage.limit")}:{" "}
                        {p.quota!.estimated_limit === null ? t("usage.unknown") : `≈${p.quota!.estimated_limit}`}
                      </span>
                    </div>
                    <QuotaLine provider={p} />
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card>
            <h2 className="mb-3 text-sm font-semibold">{t("usage.ledger")}</h2>
            {usage.ledger.length === 0 ? (
              <p className="text-sm text-muted">{t("usage.empty")}</p>
            ) : (
              <ul className="divide-y divide-line">
                {usage.ledger.map((e) => (
                  <li key={e.id} className="flex items-center justify-between py-2 text-sm">
                    <span>
                      {t(`usage.reason_${e.reason}`, { defaultValue: e.reason })}
                      <span className="ml-2 text-[11px] text-muted">{fmt.format(new Date(e.created_at))}</span>
                    </span>
                    <span className={e.delta > 0 ? "text-ok" : "text-muted"}>
                      {e.delta > 0 ? `+${e.delta}` : e.delta}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
