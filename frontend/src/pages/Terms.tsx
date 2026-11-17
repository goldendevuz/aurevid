// SPDX-License-Identifier: AGPL-3.0-or-later
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card } from "../components/ui";

const SECTIONS = ["s1", "s2", "s3", "s4", "s5", "s6"] as const;

export default function Terms() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <Link to="/" className="text-xs text-muted hover:text-ink">← aurevid</Link>
      <Card className="mt-3">
        <h1 className="text-xl font-semibold tracking-tight">{t("terms.title")}</h1>
        <p className="mt-1 text-xs text-muted">{t("terms.updated")}</p>
        {SECTIONS.map((s) => (
          <section key={s} className="mt-5">
            <h2 className="text-sm font-semibold text-amber">{t(`terms.${s}h`)}</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink/90">{t(`terms.${s}`)}</p>
          </section>
        ))}
      </Card>
    </div>
  );
}
