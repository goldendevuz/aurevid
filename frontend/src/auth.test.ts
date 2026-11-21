// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { nextPath } from "./auth";

describe("nextPath", () => {
  it("lands in the Studio (/create) by default, since / is the landing page", () => {
    expect(nextPath(null)).toBe("/create");
    expect(nextPath({})).toBe("/create");
  });
  it("keeps an internal next path and rejects external ones", () => {
    expect(nextPath({ next: "/marketing" })).toBe("/marketing");
    expect(nextPath({ next: "//evil.example" })).toBe("/create");
    expect(nextPath({ next: "https://evil.example" })).toBe("/create");
  });
});
