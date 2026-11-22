// SPDX-License-Identifier: AGPL-3.0-or-later
import { describe, expect, it } from "vitest";
import ts from "typescript";

// Allowlist for brand, vendor names, and admin page per Q1 instructions.
// Size limit: <= 15 entries.
export const ALLOWLIST: Record<string, string[]> = {
  // Admin is allowed to remain English as internal admin tooling
  "../pages/Admin.tsx": ["__ALL__"],
  "../components/Layout.tsx": ["Aurevid", "aurevid"],
  "../components/ModelPicker.tsx": ["Seedance", "FLUX", "Wan", "OpenRouter"],
  "../pages/Landing.tsx": ["Aurevid", "AGPL-3.0"],
  "../pages/Pricing.tsx": ["OpenRouter"],
};

describe("hardcoded user-visible strings", () => {
  const sources = import.meta.glob<string>(
    ["../pages/**/*.tsx", "../components/**/*.tsx", "!../**/*.test.tsx", "!../**/*.test.ts"],
    {
      query: "?raw",
      import: "default",
      eager: true,
    },
  );

  it("allowlist conforms to rules and size limit <= 15", () => {
    const totalEntries = Object.values(ALLOWLIST).flat().length;
    expect(totalEntries).toBeLessThanOrEqual(15);
  });

  it("finds no hard-coded English in pages and components", () => {
    const findings: { file: string; line: number; type: string; text: string }[] = [];

    for (const [file, code] of Object.entries(sources)) {
      const fileAllow = ALLOWLIST[file] || [];
      if (fileAllow.includes("__ALL__")) {
        continue;
      }

      const sf = ts.createSourceFile(file, code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

      function visit(node: ts.Node) {
        // Ignore code, pre, svg elements
        if (ts.isJsxElement(node)) {
          const tag = node.openingElement.tagName.getText(sf);
          if (["code", "pre", "svg"].includes(tag)) return;
        }
        if (ts.isJsxSelfClosingElement(node)) {
          const tag = node.tagName.getText(sf);
          if (["code", "pre", "svg"].includes(tag)) return;
        }

        // (a) JSX text nodes
        if (ts.isJsxText(node)) {
          const raw = node.text;
          const trimmed = raw.trim();
          if (/[A-Za-z]{3,}/.test(trimmed)) {
            // Check each line or trimmed segment
            const lines = trimmed.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
            for (const line of lines) {
              if (/[A-Za-z]{3,}/.test(line)) {
                if (!fileAllow.includes(line)) {
                  const { line: lineNum } = sf.getLineAndCharacterOfPosition(node.getStart(sf));
                  findings.push({ file, line: lineNum + 1, type: "jsx_text", text: line });
                }
              }
            }
          }
        }

        // (b) string-literal attribute values
        if (ts.isJsxAttribute(node)) {
          const attr = node.name.getText(sf);
          if (["placeholder", "title", "aria-label", "alt", "label"].includes(attr)) {
            if (node.initializer && ts.isStringLiteral(node.initializer)) {
              const val = node.initializer.text.trim();
              if (/[A-Za-z]{3,}/.test(val)) {
                if (!fileAllow.includes(val)) {
                  const { line: lineNum } = sf.getLineAndCharacterOfPosition(node.getStart(sf));
                  findings.push({ file, line: lineNum + 1, type: `attr:${attr}`, text: val });
                }
              }
            }
          }
        }

        ts.forEachChild(node, visit);
      }

      visit(sf);
    }

    if (findings.length > 0) {
      console.log(`TOTAL_FINDINGS: ${findings.length}`);
      const grouped: Record<string, string[]> = {};
      for (const f of findings) {
        grouped[f.file] = grouped[f.file] || [];
        grouped[f.file].push(`${f.line} [${f.type}]: ${f.text}`);
      }
      for (const [file, list] of Object.entries(grouped)) {
        console.log(`\n=== ${file} (${list.length}) ===\n` + list.join("\n"));
      }
    }

    expect(findings).toEqual([]);
  });
});
