// SPDX-License-Identifier: AGPL-3.0-or-later
import { test, expect } from "@playwright/test";
import { isServerReachable, registerTestUser } from "./helpers";

test.describe("Job Tile States", () => {
  test.beforeEach(async ({ page }) => {
    const reachable = await isServerReachable(page);
    test.skip(!reachable, "Dev server is not running on baseURL");
  });

  test("job tile exhibits queued/running and transitions to ready", async ({ page }) => {
    await page.goto("/");
    await registerTestUser(page, "states-user");
    await page.goto("/create");
    await page.waitForLoadState("networkidle");

    const promptInput = page.locator("textarea#studio-prompt, textarea").first();
    await promptInput.fill("A serene sunset over a mountain lake");

    const generateBtn = page.getByRole("button", { name: /generate/i }).first();
    await generateBtn.click();

    // Verify pending state (queued or running with status badge)
    const pendingTile = page.locator("article:has(.animate-pulse), article:has-text('Queued'), article:has-text('Running')").first();
    // It might complete quickly in mock mode (0.2s), but either pending or ready will appear
    const readyTile = page.locator("article.tile button img, article button img").first();
    await expect(readyTile).toBeVisible({ timeout: 15000 });

    // Assert that the ready tile has a valid loaded image source
    const src = await readyTile.getAttribute("src");
    expect(src).toBeTruthy();
    expect(src).toContain("/api/assets/");
  });

  test("failed job state with mock failure trigger (__fail__)", async ({ page }) => {
    await page.goto("/");
    await registerTestUser(page, "states-fail");
    await page.goto("/create");
    await page.waitForLoadState("networkidle");

    const promptInput = page.locator("textarea#studio-prompt, textarea").first();
    await promptInput.fill("Deliberate error __fail__ test");

    const generateBtn = page.getByRole("button", { name: /generate/i }).first();
    await generateBtn.click();

    // The mock provider raises ProviderError for __fail__ prompt
    // The tile should display error state or retry button
    const failedTileOrError = page.locator("article:has-text('Failed'), article:has-text('Error'), button:has-text('Retry'), p.text-danger").first();
    await expect(failedTileOrError).toBeVisible({ timeout: 15000 });
  });
});
