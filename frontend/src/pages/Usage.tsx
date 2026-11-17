// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { Card, ErrorText } from "../components/ui";
import type { Usage } from "../types";

export default function UsagePage() {
  const { t, i18n } = useTranslation();
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<Usage>("/api/credits").then(setUsage).catch(setError);
  }, []);

  const pct = usage ? Math.min(100, (usage.jobs_today / usage.daily_job_limit) * 100) : 0;
  const fmt = new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" });

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold tracking-tight">{t("usage.title")}</h1>
      <ErrorText error={error} />
      {usage && (
        <>
          <Card>
            <p className="text-xs uppercase tracking-wide text-muted">{t("usage.balance")}</p>
            <p className="mt-1 text-4xl font-semibold text-amber">{usage.balance}</p>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-raised">
              <div className="h-full bg-amber" style={{ width: `${pct}%` }} />
            </div>
            <p className="mt-2 text-xs text-muted">
              {t("usage.today", { used: usage.jobs_today, limit: usage.daily_job_limit })}
            </p>
            <p className="mt-3 text-xs text-muted">{t("usage.note")}</p>
          </Card>
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
