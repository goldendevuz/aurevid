// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import { readCookie } from "./api";

describe("readCookie", () => {
  it("reads a named cookie and decodes it", () => {
    expect(readCookie("av_csrf", "a=1; av_csrf=abc%3D%3D; b=2")).toBe("abc==");
  });
  it("returns null when missing and does not match prefixes", () => {
    expect(readCookie("av_csrf", "xav_csrf=1; av_csrf_old=2")).toBeNull();
  });
});
