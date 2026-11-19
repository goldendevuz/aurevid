// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import en from "./locales/en.json";
import ru from "./locales/ru.json";
import uz from "./locales/uz.json";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

function placeholders(obj: object): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  const walk = (o: object, p: string) =>
    Object.entries(o).forEach(([k, v]) =>
      typeof v === "string" ? (out[p + k] = (v.match(/{{\w+}}/g) ?? []).sort()) : walk(v, `${p}${k}.`),
    );
  walk(obj, "");
  return out;
}

describe("locales", () => {
  const base = keys(en).sort();
  it.each([["uz", uz], ["ru", ru]])("%s has exactly the same keys as en", (_, loc) => {
    expect(keys(loc).sort()).toEqual(base);
  });
  it.each([["uz", uz], ["ru", ru]])("%s keeps the same {{placeholders}}", (_, loc) => {
    expect(placeholders(loc)).toEqual(placeholders(en));
  });
  it("covers every backend error code", () => {
    const codes = [
      "invalid_credentials", "registration_failed", "rate_limited", "csrf_failed", "bad_origin",
      "insufficient_credits", "daily_limit_reached", "prompt_rejected", "provider_key_required",
      "unknown_model", "unknown_preset", "aspect_ratio_unsupported", "count_too_high",
      "validation_error", "captcha_required", "captcha_failed", "account_blocked", "invalid_image",
      "file_too_large", "byok_disabled", "bad_fields", "not_found", "not_authenticated",
      "invalid_session", "duplicate_request", "duration_unsupported", "image_input_unsupported",
      "image_required", "provider_cooldown", "upscale_unsupported", "upscaler_disabled",
      "already_that_large", "too_many_active_jobs", "queue_full", "free_share_used", "free_month_used", "job_not_finished",
      "recipe_step_unavailable", "recipe_step_failed",
      "already_that_large", "too_many_active_jobs", "queue_full", "free_share_used",
      "payments_disabled", "unknown_pack", "payment_gateway_error",
    ];
    for (const c of codes) expect(Object.keys(en.errors)).toContain(c);
  });
});
