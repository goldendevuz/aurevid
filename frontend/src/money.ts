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

/** Only https URLs from our own API are followed when starting a payment. */
export function isSafePayUrl(url: string, origin: string): boolean {
  try {
    const u = new URL(url, origin);
    return u.protocol === "https:" || u.origin === origin;
  } catch {
    return false;
  }
}
