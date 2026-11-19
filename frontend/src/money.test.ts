// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { formatSom, isSafePayUrl, pricePerCredit } from "./money";

describe("formatSom", () => {
  it("groups thousands with spaces", () => {
    expect(formatSom(15000)).toBe("15 000");
    expect(formatSom(119000)).toBe("119 000");
    expect(formatSom(1234567)).toBe("1 234 567");
    expect(formatSom(999)).toBe("999");
  });
  it("shows one decimal only when needed", () => {
    expect(pricePerCredit(15000, 100)).toBe("150");
    expect(pricePerCredit(39000, 300)).toBe("130");
    expect(pricePerCredit(10000, 3)).toBe("3 333,3");
  });
});

describe("isSafePayUrl", () => {
  const origin = "https://aurevid.test";
  it("allows https and same-origin pages", () => {
    expect(isSafePayUrl("https://inpay.uz/pay/abc", origin)).toBe(true);
    expect(isSafePayUrl("https://aurevid.test/credits?order=1", origin)).toBe(true);
  });
  it("refuses script and plain-http URLs", () => {
    expect(isSafePayUrl("javascript:alert(1)", origin)).toBe(false);
    expect(isSafePayUrl("http://evil.example/", origin)).toBe(false);
  });
});
