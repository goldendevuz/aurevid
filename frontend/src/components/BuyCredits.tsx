// SPDX-License-Identifier: AGPL-3.0-or-later
// Optional credit packs. The return page never trusts its query string: it only takes the order
// id from it and asks our API for the real status.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { isSafePayUrl, formatSom, pricePerCredit } from "../money";
import type { CreditPacks, PaymentOrder } from "../types";
import { Badge, Button, Card, ErrorText } from "./ui";

const POLL_MS = 2000;
const MAX_POLLS = 90; // ~3 minutes
const FINAL = new Set(["paid", "failed", "expired"]);

function useOrderPolling(orderId: string | null, onPaid: () => void) {
  const [order, setOrder] = useState<PaymentOrder | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const paidRef = useRef(onPaid);
  useEffect(() => {
    paidRef.current = onPaid;
  });

  useEffect(() => {
    if (!orderId) return;
    let stopped = false;
    let polls = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setOrder(null);
    setTimedOut(false);
    setError(null);
    const tick = async () => {
      polls += 1;
      try {
        const o = await api<PaymentOrder>(`/api/payments/orders/${encodeURIComponent(orderId)}`);
        if (stopped) return;
        setOrder(o);
        if (FINAL.has(o.status)) {
          if (o.status === "paid") paidRef.current();
          return;
        }
      } catch (e) {
        if (stopped) return;
        if (e instanceof ApiError && e.status === 404) {
          setError(e);
          return;
        }
      }
      if (polls >= MAX_POLLS) setTimedOut(true);
      else timer = setTimeout(() => void tick(), POLL_MS);
    };
    void tick();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [orderId]);

  return { order, timedOut, error };
}

function OrderResult({ orderId, onPaid }: { orderId: string; onPaid: () => void }) {
  const { t } = useTranslation();
  const { order, timedOut, error } = useOrderPolling(orderId, onPaid);
  if (error) return <ErrorText error={error} />;
  const status = order?.status ?? "pending";
  if (status === "paid")
    return <p role="status" className="rounded-lg border border-ok/30 bg-ok/10 px-3 py-2 text-sm text-ok">{t("buy.paid", { count: order!.credits })}</p>;
  if (status === "failed" || status === "expired")
    return <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{t(`buy.${status}`)}</p>;
  if (timedOut) return <p role="status" className="rounded-lg border border-line px-3 py-2 text-sm text-muted">{t("buy.stillPending")}</p>;
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-sm">
      <span className="inline-block size-4 animate-spin rounded-full border-2 border-accent border-t-transparent" aria-hidden />
      <span>
        {t("buy.checking")}
        <span className="block text-xs text-muted">{t("buy.checkingHint")}</span>
      </span>
    </div>
  );
}

export function BuyCredits({ onPaid }: { onPaid: () => void }) {
  const { t, i18n } = useTranslation();
  const [params] = useSearchParams();
  const orderId = params.get("order");
  const [catalog, setCatalog] = useState<CreditPacks | null>(null);
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const loadOrders = () => api<PaymentOrder[]>("/api/payments/orders").then(setOrders).catch(() => undefined);
  useEffect(() => {
    api<CreditPacks>("/api/payments/packs").then(setCatalog).catch(setError);
    void loadOrders();
  }, []);

  const buy = async (packId: string) => {
    setError(null);
    setBusy(packId);
    try {
      const r = await api<{ order_id: string; pay_url: string }>("/api/payments/orders", {
        method: "POST",
        body: { pack_id: packId },
      });
      if (!isSafePayUrl(r.pay_url, window.location.origin)) throw new ApiError("payment_gateway_error", 502);
      window.location.assign(r.pay_url);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  };

  const fmt = new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short" });
  const enabled = catalog?.enabled ?? false;

  return (
    <>
      <Card>
        <h2 className="text-sm font-semibold">{t("buy.title")}</h2>
        <p className="mb-4 mt-1 text-xs text-muted">{t("buy.subtitle")}</p>
        {orderId && (
          <div className="mb-4">
            <OrderResult
              orderId={orderId}
              onPaid={() => {
                onPaid();
                void loadOrders();
              }}
            />
          </div>
        )}
        {catalog && (
          <ul className="grid gap-3 sm:grid-cols-3">
            {catalog.packs.map((p) => (
              <li key={p.id} className="flex flex-col rounded-2xl border border-line bg-raised/40 p-4">
                <p className="text-2xl font-semibold tabular-nums">{t("buy.credits", { count: p.credits })}</p>
                <p className="mt-1 text-sm tabular-nums">{t("buy.price", { price: formatSom(p.amount_uzs) })}</p>
                <p className="mt-0.5 text-[11px] text-muted tabular-nums">
                  {t("buy.perCredit", { price: pricePerCredit(p.amount_uzs, p.credits) })}
                </p>
                <Button className="mt-4" size="sm" disabled={!enabled || busy !== null} onClick={() => void buy(p.id)}>
                  {busy === p.id ? t("buy.redirecting") : t("buy.button")}
                </Button>
              </li>
            ))}
          </ul>
        )}
        {catalog && !enabled && <p className="mt-3 text-xs text-muted">{t("buy.comingSoon")}</p>}
        <ErrorText error={error} />
      </Card>
      {orders.length > 0 && (
        <Card>
          <h2 className="mb-3 text-sm font-semibold">{t("buy.orders")}</h2>
          <ul className="divide-y divide-line">
            {orders.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>
                  {t("buy.credits", { count: o.credits })}
                  <span className="ml-2 text-[11px] text-muted">{fmt.format(new Date(o.created_at))}</span>
                </span>
                <span className="flex items-center gap-2 tabular-nums">
                  <span className="text-xs text-muted">{t("buy.price", { price: formatSom(o.amount_uzs) })}</span>
                  <Badge tone={o.status === "paid" ? "ok" : o.status === "pending" || o.status === "created" ? "muted" : "danger"}>
                    {t(`buy.status_${o.status}`)}
                  </Badge>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
