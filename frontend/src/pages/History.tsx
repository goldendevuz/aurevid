// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import JobCard from "../components/JobCard";
import { Button, Card, ErrorText } from "../components/ui";
import type { Job } from "../types";

const PAGE = 20;

export default function History() {
  const { t } = useTranslation();
  const [favorites, setFavorites] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [more, setMore] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(
    async (before?: string) => {
      const q = new URLSearchParams({ limit: String(PAGE), favorites: String(favorites) });
      if (before) q.set("before", before);
      const page = await api<Job[]>(`/api/jobs?${q}`);
      setJobs((prev) => (before ? [...prev, ...page] : page));
      setMore(page.length === PAGE);
    },
    [favorites],
  );

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  const tab = (active: boolean) =>
    `rounded-md px-3 py-1.5 text-sm ${active ? "bg-raised text-ink" : "text-muted hover:text-ink"}`;

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <h1 className="mr-4 text-xl font-semibold tracking-tight">{t("history.title")}</h1>
        <button className={tab(!favorites)} onClick={() => setFavorites(false)}>{t("history.all")}</button>
        <button className={tab(favorites)} onClick={() => setFavorites(true)}>{t("history.favorites")}</button>
      </div>
      <ErrorText error={error} />
      {jobs.length === 0 ? (
        <Card className="text-center text-sm text-muted">{t("history.empty")}</Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs.map((j) => (
            <JobCard key={j.id} job={j} onChange={(u) => setJobs((p) => p.map((x) => (x.id === u.id ? u : x)))} />
          ))}
        </div>
      )}
      {more && (
        <div className="mt-6 text-center">
          <Button variant="ghost" onClick={() => void load(jobs[jobs.length - 1]?.created_at)}>
            {t("history.loadMore")}
          </Button>
        </div>
      )}
    </div>
  );
}
