// SPDX-License-Identifier: AGPL-3.0-or-later
// Cloudflare Turnstile widget. Rendered only when VITE_TURNSTILE_SITE_KEY is set.
import { useEffect, useRef } from "react";

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: { sitekey: string; callback: (token: string) => void }) => string;
      remove: (id: string) => void;
    };
  }
}

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;
const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export const turnstileEnabled = Boolean(SITE_KEY);

export default function Turnstile({ onToken }: { onToken: (token: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!SITE_KEY || !ref.current) return;
    let widgetId: string | undefined;
    const mount = () => {
      if (window.turnstile && ref.current) {
        widgetId = window.turnstile.render(ref.current, { sitekey: SITE_KEY, callback: onToken });
      }
    };
    if (window.turnstile) mount();
    else {
      const s = document.createElement("script");
      s.src = SCRIPT_SRC;
      s.async = true;
      s.onload = mount;
      document.head.appendChild(s);
    }
    return () => {
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
  }, [onToken]);
  if (!SITE_KEY) return null;
  return <div ref={ref} className="mt-4" />;
}
