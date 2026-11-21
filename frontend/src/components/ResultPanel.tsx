// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ApiError } from "../api";
import type { Job } from "../types";
import { Icon } from "./icons";
import { Badge, ErrorText } from "./ui";

/**
 * Right-hand preview of the Studio workspace (lg+). It only presents state the Studio already has:
 * a submit error, the job being watched, or a comparison run. Job media is drawn by the caller's JobCard.
 */
export default function ResultPanel({
  job,
  error,
  compare,
  renderJob,
}: {
  job: Job | undefined;
  error: unknown;
  compare?: ReactNode;
  renderJob: (job: Job) => ReactNode;
}) {
  const { t } = useTranslation();
  const out = error instanceof ApiError && error.code === "insufficient_credits";
  const running = job?.status === "queued" || job?.status === "running";

  let body: ReactNode;
  let badge: ReactNode = null;
  if (compare) {
    body = compare;
  } else if (error) {
    body = out ? (
      <div className="rounded-2xl border border-accent-2/40 bg-accent-2/10 p-6 text-center">
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-raised text-accent-2">
          <Icon name="coins" size={22} />
        </div>
        <h3 className="text-2xl">{t("studio.panel.creditsTitle")}</h3>
        <p className="mx-auto mt-2 max-w-xs text-sm text-muted">{t("studio.panel.creditsHint")}</p>
        <Link to="/credits" className="btn-aurora mt-5 inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold">
          <Icon name="bolt" size={16} />
          {t("studio.panel.creditsCta")}
        </Link>
      </div>
    ) : (
      <div className="rounded-2xl border border-danger/30 bg-danger/5 p-5">
        <h3 className="text-xl">{t("studio.panel.errorTitle")}</h3>
        <ErrorText error={error} />
      </div>
    );
  } else if (job && running) {
    body = (
      <div className="grid place-items-center gap-4 rounded-2xl border border-white/10 bg-bg/50 px-6 py-14 text-center">
        <div className="neon-orbit" aria-hidden />
        <div>
          <h3 className="text-2xl">{t("studio.panel.generatingTitle")}</h3>
          <p className="mt-1 text-sm text-muted">{t("studio.panel.generatingHint")}</p>
        </div>
        <ul className="flex flex-wrap justify-center gap-2 font-mono text-[11px] text-muted">
          <li className="rounded-md bg-raised px-1.5 py-0.5 text-ink/90">{job.model_label ?? job.model.split("/").pop()}</li>
          {job.status === "queued" && job.queue_position != null && (
            <li className="rounded-md bg-raised px-1.5 py-0.5">{t("studio.panel.queue", { count: job.queue_position })}</li>
          )}
          {job.eta_seconds != null && job.eta_seconds > 0 && (
            <li className="rounded-md bg-raised px-1.5 py-0.5">{t("studio.panel.eta", { seconds: Math.round(job.eta_seconds) })}</li>
          )}
        </ul>
      </div>
    );
  } else if (job) {
    if (job.status === "done") badge = <Badge tone="live">{t("studio.panel.ready")}</Badge>;
    body = renderJob(job);
  } else {
    body = (
      <div className="grid place-items-center gap-3 rounded-2xl border border-dashed border-white/15 bg-bg/40 px-6 py-16 text-center">
        <div className="grid h-14 w-14 place-items-center rounded-2xl bg-raised text-accent shadow-[0_0_24px_-6px_rgb(255_62_138/0.7)]">
          <Icon name="sparkle" size={24} />
        </div>
        <h3 className="text-2xl">{t("studio.panel.emptyTitle")}</h3>
        <p className="max-w-xs text-sm text-muted">{t("studio.panel.emptyHint")}</p>
      </div>
    );
  }

  return (
    <aside
      aria-label={t("studio.panel.region")}
      className="glass ring-aurora rounded-[28px] p-4 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto"
    >
      <div className="mb-3 flex items-center justify-between gap-2 px-1">
        <h2 className="text-lg tracking-[0.04em]">{t("studio.panel.title")}</h2>
        {badge}
      </div>
      <div aria-live="polite">{body}</div>
    </aside>
  );
}
