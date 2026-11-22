import { useTranslation } from "react-i18next";
// SPDX-License-Identifier: AGPL-3.0-or-later
// Cloudflare Turnstile widget. Rendered only when VITE_TURNSTILE_SITE_KEY is set.
import { useEffect, useRef, useState, useCallback } from "react";

declare global {
  interface Window {
    turnstile?: {
      render: (
        el: HTMLElement,
        opts: {
          sitekey: string;
          callback: (token: string) => void;
          "error-callback"?: (code: string | number) => void;
          "expired-callback"?: () => void;
          theme?: "auto" | "light" | "dark";
        }
      ) => string;
      reset: (id?: string) => void;
      remove: (id: string) => void;
    };
  }
}

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY;
const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export const turnstileEnabled = Boolean(SITE_KEY);

const ERROR_DESCRIPTIONS: Record<string, string> = {
  "110200": "Domain mismatch: this domain is not allowed in Cloudflare Turnstile settings.",
  "110100": "Invalid sitekey: check VITE_TURNSTILE_SITE_KEY configuration.",
  "300030": "Challenge failed: browser challenge could not be completed.",
  "600010": "Challenge timed out.",
};

export default function Turnstile({ onToken }: { onToken: (token: string) => void }) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | undefined>(undefined);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const resetWidget = useCallback(() => {
    setErrorMessage(null);
    onToken("");
    if (window.turnstile && widgetIdRef.current) {
      window.turnstile.reset(widgetIdRef.current);
    }
  }, [onToken]);

  useEffect(() => {
    if (!SITE_KEY || !ref.current) return;

    const mount = () => {
      if (window.turnstile && ref.current) {
        // Clear previous widget if any
        if (widgetIdRef.current) {
          try {
            window.turnstile.remove(widgetIdRef.current);
          } catch {
            // ignore cleanup error
          }
        }
        widgetIdRef.current = window.turnstile.render(ref.current, {
          sitekey: SITE_KEY,
          theme: "dark",
          callback: (token: string) => {
            setErrorMessage(null);
            onToken(token);
          },
          "error-callback": (code: string | number) => {
            onToken("");
            const codeStr = String(code);
            const hint = ERROR_DESCRIPTIONS[codeStr] || `Cloudflare Turnstile error (${codeStr})`;
            console.error(`[Turnstile] Verification failed [${codeStr}]: ${hint}`);
            setErrorMessage(hint);
          },
          "expired-callback": () => {
            onToken("");
            setErrorMessage("Verification expired. Please retry.");
          },
        });
      }
    };

    if (window.turnstile) {
      mount();
    } else {
      const existingScript = document.querySelector(`script[src="${SCRIPT_SRC}"]`);
      if (existingScript) {
        existingScript.addEventListener("load", mount);
      } else {
        const s = document.createElement("script");
        s.src = SCRIPT_SRC;
        s.async = true;
        s.onload = mount;
        document.head.appendChild(s);
      }
    }

    return () => {
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          // ignore cleanup error
        }
      }
    };
  }, [onToken]);

  if (!SITE_KEY) return null;

  return (
    <div className="mt-4">
      <div ref={ref} />
      {errorMessage && (
        <div className="mt-2 text-xs text-danger flex items-center justify-between gap-2">
          <span>{errorMessage}</span>
          <button
            type="button"
            onClick={resetWidget}
            className="underline hover:text-ink text-[11px] whitespace-nowrap"
          >
            {t("common.retry")}
          </button>
        </div>
      )}
    </div>
  );
}
