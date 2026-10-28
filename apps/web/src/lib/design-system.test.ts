import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/** Guards the design system against silent drift.
 *
 * These scan source text rather than behaviour, following the precedent set by
 * `polling-consolidation.test.ts`: a consistency pass that is done once and never
 * enforced decays the moment the next page is written. Each rule here corresponds to a
 * rule in DESIGN.md, and each one had real violations in the codebase before the
 * redesign, so none of them is hypothetical.
 */

const SRC = join(__dirname, "..");
const LANDING = join(SRC, "app", "page.tsx");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(full)) out.push(full);
  }
  return out;
}

/** Comments legitimately describe banned patterns in order to explain why they are
 * banned, so a scanner that cannot tell code from prose would fail on the explanation.
 * Strings are kept: user-visible copy is exactly what several of these rules police. */
function code(file: string): string {
  return readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const ALL = walk(SRC).filter((f) => !f.endsWith(".test.ts"));
const rel = (f: string) => relative(SRC, f).replace(/\\/g, "/");

describe("colour", () => {
  it("uses semantic tokens, never raw Tailwind palette colours", () => {
    // A raw palette colour cannot respond to a token change, so one `bg-sky-500` in a
    // chart ramp silently outlives every future palette revision.
    const pattern =
      /\b(?:text|bg|border|fill|stroke|ring|from|to|via)-(?:slate|zinc|gray|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/;
    const bad = ALL.filter((f) => pattern.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });

  it("has no hardcoded hex colours in components", () => {
    const bad = ALL.filter((f) => /["'`]#[0-9a-fA-F]{3,8}["'`]/.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });

  it("has no text-white or bg-white", () => {
    // White is only ever correct as a token's paired foreground (`text-primary-
    // foreground`), which stays correct if the token changes.
    const bad = ALL.filter((f) => /\b(?:text|bg)-white\b/.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });
});

describe("theme", () => {
  it("has no dark: variants", () => {
    // The app has no theme provider and never applies `.dark`, so a dark: variant is
    // unreachable code that silently diverges from the light styles beside it.
    const bad = ALL.filter((f) => /\bdark:/.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });

  it("does not branch on prefers-color-scheme in components", () => {
    const bad = ALL.filter((f) => /prefers-color-scheme/.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });
});

describe("typography", () => {
  it("stays within the weight scale", () => {
    // The scale tops out at 600. Emphasis comes from size and colour.
    const bad = ALL.filter((f) => /\bfont-(?:extrabold|black)\b/.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });

  it("has no sub-12px micro-labels in app chrome", () => {
    // AtsResumeBuilder is exempt: it renders a printed A4 document, where 11px is a
    // legitimate size for body copy on paper. Every other surface is app chrome.
    const bad = ALL.filter(
      (f) => !f.includes("AtsResumeBuilder") && /text-\[(?:9|10|11)px\]/.test(code(f)),
    ).map(rel);
    expect(bad).toEqual([]);
  });
});

describe("elevation", () => {
  it("uses the three elevation tokens, not Tailwind's shadow scale", () => {
    const bad = ALL.filter((f) =>
      /\bshadow-(?:sm|md|lg|xl|2xl)\b/.test(code(f)),
    ).map(rel);
    expect(bad).toEqual([]);
  });
});

describe("copy", () => {
  it("contains no em-dashes or en-dashes in code", () => {
    // These read as an LLM signature in UI copy. A spaced hyphen, comma or colon
    // carries the same meaning. Scoped to code rather than the raw file: prose in
    // comments is not user-visible, and several comments quote the banned form in
    // order to explain the rule.
    const bad = ALL.filter((f) => /[—–]/.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });

  it("uses no emoji as UI", () => {
    // One icon family (lucide). An emoji is also unlabelled for assistive tech: the
    // interview mic control was once a bare microphone emoji with no accessible name.
    const emoji =
      /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{1F000}-\u{1F02F}]/u;
    const bad = ALL.filter((f) => emoji.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });
});

describe("motion", () => {
  it("keeps scroll-linked motion out of the app", () => {
    // The landing page is the one expressive surface; app screens animate on state
    // change only, so a scroll listener in an app route is out of system.
    const scrollMotion = /\b(?:useScroll|useTransform|whileInView|useSpring)\b/;
    const bad = ALL.filter(
      (f) => f !== LANDING && !f.includes("landing") && scrollMotion.test(code(f)),
    ).map(rel);
    expect(bad).toEqual([]);
  });
});

describe("evidence conventions", () => {
  it("keeps the evidence primitives in use", () => {
    // These components existed with ZERO importers while 33 call sites rendered bare,
    // unattributable numbers. Building the honest-score UI and then not wiring it up is
    // the exact regression this guards: a score without provenance is the product's
    // central claim, not a detail.
    const consumers = ALL.filter(
      (f) =>
        !f.includes("ScoreDisplay") &&
        /\b(?:ScoreDisplay|EvidencePopover|ConfidenceBadge)\b/.test(code(f)),
    );
    expect(consumers.length).toBeGreaterThan(0);
  });

  it("never renders a missing score as zero or a bare dash", () => {
    // "N/A" and an em-dash both collapse "not measured" into "measured and bad".
    const bad = ALL.filter((f) => /["'`](?:N\/A|n\/a)["'`]/i.test(code(f))).map(rel);
    expect(bad).toEqual([]);
  });
});
