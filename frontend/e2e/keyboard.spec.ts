// SPDX-License-Identifier: AGPL-3.0-or-later
import { test, expect } from "@playwright/test";
import { isServerReachable, registerTestUser } from "./helpers";

test.describe("Keyboard Accessibility & Focus Management", () => {
  test.beforeEach(async ({ page }) => {
    const reachable = await isServerReachable(page);
    test.skip(!reachable, "Dev server is not running on baseURL");
  });

  test("ModelPicker focus trap, Escape to close, and focus return to trigger", async ({ page }) => {
    await page.goto("/");
    await registerTestUser(page, "kbd-mp");
    await page.goto("/create");
    await page.waitForLoadState("networkidle");

    // Locate the model picker trigger button
    const trigger = page.locator("button:has-text('Change'), button:has(span:has-text('Change'))").first();
    await expect(trigger).toBeVisible({ timeout: 5000 });
    await trigger.focus();
    await trigger.click();

    // Dialog should be open
    const dialog = page.locator("div[role='dialog']#model-picker-title, div[role='dialog']:has(#model-picker-title)");
    await expect(dialog).toBeVisible();

    // Verify Tab cycles inside the dialog (focus trap)
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press("Tab");
      const isInside = await page.evaluate(() => {
        const d = document.querySelector("div[role='dialog']");
        return d ? d.contains(document.activeElement) : false;
      });
      expect(isInside).toBe(true);
    }

    // Verify Shift+Tab cycles backwards inside dialog
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press("Shift+Tab");
      const isInside = await page.evaluate(() => {
        const d = document.querySelector("div[role='dialog']");
        return d ? d.contains(document.activeElement) : false;
      });
      expect(isInside).toBe(true);
    }

    // Esc closes dialog and returns focus to trigger
    await page.keyboard.press("Escape");
    await expect(dialog).not.toBeVisible();
    await expect(trigger).toBeFocused();
  });

  test("Lightbox focus trap, Escape to close, and focus return to tile", async ({ page }) => {
    await page.goto("/");
    await registerTestUser(page, "kbd-lb");
    await page.goto("/create");
    await page.waitForLoadState("networkidle");

    // Create an image job using the mock provider
    const promptInput = page.locator("textarea#studio-prompt, textarea[placeholder*='linen table'], textarea").first();
    await promptInput.fill("Keyboard lightbox test");
    const generateBtn = page.getByRole("button", { name: /generate/i }).first();
    await generateBtn.click();

    // Wait for the job tile to complete and display the ready image
    const tileTrigger = page.locator("article.tile button, article button:has(img)").first();
    await expect(tileTrigger).toBeVisible({ timeout: 15000 });

    // Click tile to open lightbox
    await tileTrigger.focus();
    await tileTrigger.click();

    // Lightbox modal dialog should be visible
    const lightboxDialog = page.locator("div[role='dialog'][aria-modal='true']");
    await expect(lightboxDialog).toBeVisible();

    // Verify Tab cycles inside lightbox
    for (let i = 0; i < 6; i++) {
      await page.keyboard.press("Tab");
      const isInside = await page.evaluate(() => {
        const lb = document.querySelector("div[role='dialog'][aria-modal='true']");
        return lb ? lb.contains(document.activeElement) : false;
      });
      expect(isInside).toBe(true);
    }

    // Esc closes lightbox and returns focus to tileTrigger
    await page.keyboard.press("Escape");
    await expect(lightboxDialog).not.toBeVisible();
    await expect(tileTrigger).toBeFocused();
  });
});
