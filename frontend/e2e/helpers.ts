// SPDX-License-Identifier: AGPL-3.0-or-later
import { type Page } from "@playwright/test";

export async function isServerReachable(page: Page): Promise<boolean> {
  try {
    const res = await page.goto("/", { timeout: 4000 });
    return Boolean(res && res.status() < 500);
  } catch {
    return false;
  }
}

// Module-level cached auth cookies to avoid hitting registration/login rate limits
let cachedCookies: any[] | null = null;

export async function ensureAuthenticated(page: Page): Promise<string> {
  const context = page.context();

  // If we already authenticated in this test run, simply inject cookies into context
  if (cachedCookies && cachedCookies.length > 0) {
    await context.addCookies(cachedCookies);
    return "e2e-persistent-user@example.com";
  }

  const email = "e2e-persistent-user@example.com";
  const password = "Password123!";

  // 1. Fetch CSRF token via page.request to populate cookie jar
  await page.request.get("/api/auth/csrf");
  const initialCookies = await context.cookies();
  const csrfCookie = initialCookies.find((c) => c.name === "av_csrf");
  const tok = csrfCookie ? csrfCookie.value : "";

  // 2. Perform authentication inside page context
  await page.evaluate(
    async ({ email, password, tok }) => {
      // Try login first
      const loginRes = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": tok },
        body: JSON.stringify({ email, password }),
      });

      if (loginRes.ok) return;

      // Register if user does not exist
      const regRes = await fetch("/api/auth/register", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": tok },
        body: JSON.stringify({ email, password, accept_terms: true }),
      });

      if (regRes.ok) return;

      // Retry login if registered concurrently
      const retry = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": tok },
        body: JSON.stringify({ email, password }),
      });
      if (retry.ok) return;

      throw new Error(`Auth failed: login=${loginRes.status}, reg=${regRes.status}`);
    },
    { email, password, tok }
  );

  // 3. Cache cookies for all subsequent tests
  cachedCookies = await context.cookies();
  return email;
}

export const registerTestUser = ensureAuthenticated;

export async function assertNoHScroll(page: Page): Promise<void> {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  if (scrollWidth > innerWidth) {
    throw new Error(`Horizontal scroll detected: scrollWidth (${scrollWidth}) > innerWidth (${innerWidth})`);
  }
}
