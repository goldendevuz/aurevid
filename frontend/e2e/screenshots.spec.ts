// SPDX-License-Identifier: AGPL-3.0-or-later
import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { isServerReachable, registerTestUser } from "./helpers";

test.describe("Real UI Screenshots (SHOTS=1)", () => {
  test.skip(!process.env.SHOTS, "Screenshots suite only runs when SHOTS=1");

  test("captures 10 authentic, distinct screens per viewport", async ({ page }, testInfo) => {
    const reachable = await isServerReachable(page);
    test.skip(!reachable, "Dev server is not running on baseURL");

    const outDir = path.resolve(process.cwd(), "../docs/img/ui-v2");
    if (!fs.existsSync(outDir)) {
      fs.mkdirSync(outDir, { recursive: true });
    }

    const label = testInfo.project.name; // "desktop" or "mobile"

    const takeShot = async (name: string, fullPage = false) => {
      await page.waitForTimeout(600);
      const filePath = path.join(outDir, `${label}-${name}.png`);
      await page.screenshot({ path: filePath, fullPage });
      expect(fs.existsSync(filePath)).toBe(true);
      const stat = fs.statSync(filePath);
      expect(stat.size).toBeGreaterThan(1000); // Must be a real non-empty screenshot
    };

    // 1. Home / Landing
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await takeShot("home");

    // 2. Pricing
    await page.goto("/pricing");
    await page.waitForLoadState("networkidle");
    await takeShot("pricing");

    // 3. Auth
    await page.goto("/login");
    await page.waitForLoadState("networkidle");
    await takeShot("auth");

    // Register user for authenticated screens
    await registerTestUser(page, `shots-${label}`);

    // 4. Studio Image
    await page.goto("/create?mode=image");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(400);
    await takeShot("studio-image");

    // 5. Studio Video
    await page.goto("/create?mode=video");
    await page.waitForLoadState("networkidle");
    const videoBtn = page.locator("button:has-text('Video'), button:has-text('video')").first();
    if (await videoBtn.isVisible()) {
      await videoBtn.click().catch(() => {});
    }
    await page.waitForTimeout(500);
    await takeShot("studio-video");

    // 6. Model Picker
    const trigger = page.locator("button:has-text('Change'), button:has(span:has-text('Change'))").first();
    await trigger.click();
    await page.waitForTimeout(400);
    // Expand inactive section if available
    const inactiveBtn = page.locator("button:has-text('Inactive'), button:has-text('Expand')").first();
    if (await inactiveBtn.isVisible()) {
      await inactiveBtn.click().catch(() => {});
      await page.waitForTimeout(300);
    }
    await takeShot("model-picker");
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);

    // 7. Director
    await page.goto("/create?mode=director");
    await page.waitForLoadState("networkidle");
    await takeShot("director");

    // 8. Library
    await page.goto("/library");
    await page.waitForLoadState("networkidle");
    await takeShot("library");

    // 9. History Tiles: Create a job in Studio so a completed tile is displayed in canvas
    await page.goto("/create?mode=image");
    await page.waitForLoadState("networkidle");
    const promptInput = page.locator("textarea#studio-prompt, textarea").first();
    await promptInput.fill("Cinematic cybernetic tiger in neon rain");
    const generateBtn = page.getByRole("button", { name: /generate/i }).first();
    await generateBtn.click();

    // Wait for the ready tile in canvas
    const readyTile = page.locator("article.tile button, article button:has(img)").first();
    await expect(readyTile).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(800);
    await takeShot("history-tiles");

    // 10. Lightbox: Click ready tile to open full modal viewer
    await readyTile.click();
    const lightboxModal = page.locator("div[role='dialog'][aria-modal='true']");
    await expect(lightboxModal).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(600);
    await takeShot("lightbox");
    await page.keyboard.press("Escape");
  });
});
