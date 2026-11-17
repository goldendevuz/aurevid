// SPDX-License-Identifier: AGPL-3.0-or-later
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Footer, Logo } from "../components/Layout";
import { Card, PageHeader } from "../components/ui";

const SECTIONS = ["s1", "s2", "s3", "s4", "s5", "s6"] as const;

export default function Terms() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-screen flex-col">
     <div className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">
      <div className="mb-8 flex items-center justify-between">
        <Logo />
        <Link to="/" className="text-xs text-muted hover:text-ink">← {t("nav.studio")}</Link>
      </div>
      <PageHeader title={t("terms.title")} subtitle={t("terms.updated")} />
      <Card>
        {SECTIONS.map((s) => (
          <section key={s} className="mt-5">
            <h2 className="text-sm font-semibold text-accent">{t(`terms.${s}h`)}</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink/90">{t(`terms.${s}`)}</p>
          </section>
        ))}
      </Card>
     </div>
     <Footer />
    </div>
  );
}
