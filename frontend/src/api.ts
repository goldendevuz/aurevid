// SPDX-License-Identifier: AGPL-3.0-or-later
// Same-origin API client. Auth lives in httpOnly cookies; we never store tokens or keys in JS.

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
  ) {
    super(code);
  }
}

export function readCookie(name: string, cookieString: string = document.cookie): string | null {
  for (const part of cookieString.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

async function ensureCsrf(): Promise<string> {
  let token = readCookie("av_csrf");
  if (!token) {
    await fetch("/api/auth/csrf", { credentials: "same-origin" });
    token = readCookie("av_csrf");
  }
  return token ?? "";
}

let refreshing: Promise<boolean> | null = null;
function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRF-Token": await ensureCsrf() },
    });
    return res.ok;
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const send = async () => {
    const headers: Record<string, string> = { ...opts.headers };
    let body: BodyInit | undefined;
    if (method !== "GET") headers["X-CSRF-Token"] = await ensureCsrf();
    if (opts.form) body = opts.form;
    else if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.body);
    }
    return fetch(path, { method, headers, body, credentials: "same-origin" });
  };

  let res = await send();
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    if (await refreshSession()) res = await send();
  }
  if (!res.ok) {
    let code = "generic";
    try {
      const data = await res.json();
      code = data?.detail?.code ?? code;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(code, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
