// SPDX-License-Identifier: AGPL-3.0-or-later
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import JobCard from "../components/JobCard";
import { Icon } from "../components/icons";
import { Button, EmptyState, ErrorText, PageHeader, Segmented } from "../components/ui";
import type { Job } from "../types";

const PAGE = 20;

export default function History() {
  const { t } = useTranslation();
  const navigate = useNavigate();
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

  return (
    <div>
      <PageHeader
        title={t("history.title")}
        actions={
          <Segmented
            label={t("history.title")}
            value={favorites ? "fav" : "all"}
            onChange={(v) => setFavorites(v === "fav")}
            options={[
              { value: "all", label: t("history.all") },
              { value: "fav", label: <span className="flex items-center gap-1.5"><Icon name="star" size={14} />{t("history.favorites")}</span> },
            ]}
          />
        }
      />
      <ErrorText error={error} />
      {jobs.length === 0 ? (
        <EmptyState icon={<Icon name="history" size={22} />} title={t("history.empty")} />
      ) : (
        <div className="grid items-start gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {jobs.map((j) => (
            <JobCard
              key={j.id}
              job={j}
              onChange={(u) => setJobs((p) => p.map((x) => (x.id === u.id ? u : x)))}
              onAnimate={(asset) => navigate("/", { state: { animate: asset } })}
              onUpscale={async (asset, target) => {
                try {
                  await api(`/api/assets/${asset.id}/upscale`, { method: "POST", body: { target } });
                  navigate("/");
                } catch (err) {
                  setError(err);
                }
              }}
            />
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
