// SPDX-License-Identifier: AGPL-3.0-or-later

/** Known providers keep a fixed colour; any new provider id falls back to a stable hash. All colours are theme tokens. */
const KNOWN: Record<string, number> = { cloudflare: 2, pollinations: 3, pollinations_video: 3, modal_video: 4, fal: 1, gpu_worker: 5 };

export function providerColor(id: string): string {
  let n = KNOWN[id];
  if (!n) {
    let h = 0;
    for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    n = (h % 5) + 1;
  }
  return `var(--color-provider-${n})`;
}

export function ProviderDot({ id, size = 8, className = "" }: { id: string; size?: number; className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-block shrink-0 rounded-full ${className}`}
      style={{ width: size, height: size, background: providerColor(id), boxShadow: `0 0 8px -1px ${providerColor(id)}` }}
    />
  );
}
