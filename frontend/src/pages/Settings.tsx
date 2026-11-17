// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { LanguageSelect } from "../components/Layout";
import { Badge, Button, Card, ErrorText, inputClass, Label, PageHeader } from "../components/ui";
import type { Provider, ProviderKeyStatus } from "../types";

function KeyForm({ provider, status, onSaved }: { provider: Provider; status?: ProviderKeyStatus; onSaved: () => void }) {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api(`/api/me/keys/${provider.id}`, { method: "PUT", body: { values } });
      setValues({}); // never keep the secret in memory longer than needed
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(err);
    }
  };
  const remove = async () => {
    await api(`/api/me/keys/${provider.id}`, { method: "DELETE" });
    onSaved();
  };

  return (
    <form onSubmit={save} className="rounded-2xl border border-line bg-raised/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold">
          {provider.name}{" "}
          <Badge tone={provider.tier === "free" ? "free" : "paid"}>
            {provider.tier === "free" ? t("studio.free") : t("studio.paid")}
          </Badge>
        </p>
        <Badge tone={status?.configured ? "ok" : "muted"}>
          {status?.configured ? t("settings.keyConfigured") : t("settings.keyNotSet")}
        </Badge>
      </div>
      <p className="mb-2 text-[11px] text-muted">{provider.notes}</p>
      <p className="mb-2 text-[11px] text-ink/80">
        {t(`settings.steps_${provider.id}`, { defaultValue: "" })}
      </p>
      <div className="mb-3 flex flex-wrap gap-3 text-xs">
        {provider.key_url && (
          <a href={provider.key_url} target="_blank" rel="noopener noreferrer" className="font-semibold text-accent hover:underline">
            🔑 {t("settings.getKey")} ↗
          </a>
        )}
        {provider.key_guide_url && (
          <a href={provider.key_guide_url} target="_blank" rel="noopener noreferrer" className="text-muted hover:text-ink hover:underline">
            {t("settings.guide")} ↗
          </a>
        )}
      </div>
      <div className="space-y-2">
        {provider.byok_fields.map((f) => (
          <div key={f}>
            <Label htmlFor={`${provider.id}-${f}`}>{t(`settings.field_${f}`, { defaultValue: f })}</Label>
            <input
              id={`${provider.id}-${f}`}
              type="password"
              autoComplete="off"
              required
              maxLength={512}
              value={values[f] ?? ""}
              onChange={(e) => setValues({ ...values, [f]: e.target.value })}
              className={inputClass}
            />
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Button type="submit">{t("settings.save")}</Button>
        {status?.configured && (
          <Button type="button" variant="ghost" onClick={() => void remove()}>{t("settings.remove")}</Button>
        )}
      </div>
      {saved && <p className="mt-2 text-xs text-ok">{t("settings.saved")}</p>}
      <ErrorText error={error} />
    </form>
  );
}

export default function Settings() {
  const { t } = useTranslation();
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [keys, setKeys] = useState<ProviderKeyStatus[]>([]);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = async () => {
    const [p, k] = await Promise.all([
      api<Provider[]>("/api/providers"),
      api<ProviderKeyStatus[]>("/api/me/keys"),
    ]);
    setProviders(p.filter((x) => x.byok));
    setKeys(k);
  };
  useEffect(() => {
    load().catch(setError);
  }, []);

  const exportData = async () => {
    const data = await api<unknown>("/api/me/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "aurevid-export.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const deleteAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api("/api/me", { method: "DELETE", body: { password } });
      setUser(null);
      navigate("/register");
    } catch (err) {
      setError(err);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageHeader title={t("settings.title")} />
      <Card>
        <Label>{t("settings.language")}</Label>
        <LanguageSelect />
      </Card>
      <Card>
        <h2 className="text-sm font-semibold">{t("settings.keys")}</h2>
        <p className="mb-4 mt-1 text-xs text-muted">{t("settings.keysHelp")}</p>
        <div className="space-y-3">
          {providers.map((p) => (
            <KeyForm key={p.id} provider={p} status={keys.find((k) => k.provider === p.id)} onSaved={() => void load()} />
          ))}
        </div>
      </Card>
      <Card>
        <h2 className="text-sm font-semibold">{t("settings.export")}</h2>
        <p className="mb-3 mt-1 text-xs text-muted">{t("settings.exportHelp")}</p>
        <Button variant="ghost" onClick={() => void exportData()}>{t("settings.export")}</Button>
      </Card>
      <Card className="border-danger/40">
        <h2 className="text-sm font-semibold text-danger">{t("settings.danger")}</h2>
        <p className="mb-3 mt-1 text-xs text-muted">{t("settings.deleteHelp")}</p>
        <form onSubmit={deleteAccount} className="space-y-2">
          <Label htmlFor="confirm-password">{t("settings.passwordToConfirm")}</Label>
          <input
            id="confirm-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
          <Button type="submit" variant="danger">{t("settings.deleteAccount")}</Button>
        </form>
        <ErrorText error={error} />
      </Card>
    </div>
  );
}
