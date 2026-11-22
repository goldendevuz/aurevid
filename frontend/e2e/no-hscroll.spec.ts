// SPDX-License-Identifier: AGPL-3.0-or-later
import { test, expect } from "@playwright/test";
import { isServerReachable, registerTestUser, assertNoHScroll } from "./helpers";

test.describe("No Horizontal Scroll", () => {
  test.beforeEach(async ({ page }) => {
    const reachable = await isServerReachable(page);
    test.skip(!reachable, "Dev server is not running on baseURL");
  });

  const publicRoutes = ["/", "/pricing", "/login", "/library"];

  for (const route of publicRoutes) {
    test(`route ${route} has no horizontal scrollbar`, async ({ page }) => {
      await page.goto(route);
      await page.waitForLoadState("networkidle");
      await assertNoHScroll(page);
    });
  }

  test("authenticated routes (/create, /create?mode=director) have no horizontal scrollbar", async ({ page }) => {
    await page.goto("/");
    await registerTestUser(page, "scroll-user");

    await page.goto("/create");
    await page.waitForLoadState("networkidle");
    await assertNoHScroll(page);

    await page.goto("/create?mode=director");
    await page.waitForLoadState("networkidle");
    await assertNoHScroll(page);
  });
});
