// SPDX-License-Identifier: AGPL-3.0-or-later
// So'm formatting: space as thousands separator (non-breaking, so prices never wrap).

const NBSP = " ";

export function formatSom(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  const [int, frac] = Math.abs(rounded).toFixed(Number.isInteger(rounded) ? 0 : 1).split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  return `${rounded < 0 ? "-" : ""}${grouped}${frac ? `,${frac}` : ""}`;
}

export function pricePerCredit(amountUzs: number, credits: number): string {
  return formatSom(credits > 0 ? amountUzs / credits : 0);
}

/**
 * Formats a USD amount for display:
 * When < $1, formatted in cents: "≈ 32¢".
 * When >= $1, formatted in dollars: "≈ $1.24".
 * `exact` contains full 4-decimal dollar string for tooltips (e.g. "$0.3241").
 */
export function formatCents(usd: number): { short: string; exact: string } {
  const exact = `$${usd.toFixed(4)}`;
  const cents = Math.round(usd * 100);
  const short = usd < 1 ? `≈ ${Math.max(1, cents)}¢` : `≈ $${usd.toFixed(2)}`;
  return { short, exact };
}

/** Only https URLs from our own API are followed when starting a payment. */
export function isSafePayUrl(url: string, origin: string): boolean {
  try {
    const u = new URL(url, origin);
    return u.protocol === "https:" || u.origin === origin;
  } catch {
    return false;
  }
}
