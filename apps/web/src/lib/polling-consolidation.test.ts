import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/** Source-level checks that the polling duplication stays gone.
 *
 * Written before the consolidation, and failing against the old code: four helpers in
 * api.ts each re-declared `intervalMs = 2000 / maxIntervalMs = 5000 / timeoutMs = 180_000`
 * and hand-rolled the same while-loop, while two page components ran their own
 * `setTimeout` loops at a different interval with no backoff and — the real defect — no
 * visibility-gating, so a backgrounded tab polled forever.
 *
 * Behaviour is covered by polling.test.ts; these assert the structure, because the
 * failure mode here is a *new* copy appearing rather than an existing one misbehaving.
 */

const API_SOURCE = readFileSync(
  fileURLToPath(new URL("./api.ts", import.meta.url)),
  "utf-8",
);

function read(relativePath: string): string {
  return readFileSync(
    fileURLToPath(new URL(relativePath, import.meta.url)),
    "utf-8",
  );
}

describe("api.ts polling helpers", () => {
  it("declares the polling constants exactly once", () => {
    // Each literal appeared four times, once per helper.
    expect(API_SOURCE.match(/maxIntervalMs\s*[:=]\s*5000/g) ?? []).toHaveLength(1);
    expect(API_SOURCE.match(/timeoutMs\s*[:=]\s*180_000/g) ?? []).toHaveLength(1);
  });

  it("implements the poll loop exactly once", () => {
    // `consecutiveErrors` is the tell: it existed in every duplicated loop body.
    const loops = API_SOURCE.match(/let consecutiveErrors = 0/g) ?? [];
    expect(loops).toHaveLength(1);
  });

  it("routes every helper through pollUntil", () => {
    const helpers = [
      "pollIngestionStatus",
      "pollMatchingStatus",
      "pollSubmissionGrading",
      "pollRankingStatus",
    ];
    for (const helper of helpers) {
      const start = API_SOURCE.indexOf(`export async function ${helper}(`);
      expect(start, `${helper} should exist`).toBeGreaterThan(-1);
      // Body is short now; take a generous window and require the delegation.
      const body = API_SOURCE.slice(start, start + 900);
      expect(body, `${helper} should delegate to pollUntil`).toContain("pollUntil");
    }
  });
});

describe("page components", () => {
  it.each([
    ["../app/(recruiter)/jobs/[id]/matches/page.tsx", "job matches"],
    ["../app/pitch-deck/[id]/page.tsx", "pitch deck"],
  ])("%s does not hand-roll its own poll loop", (path) => {
    // Strip comments before scanning: both files legitimately *describe* the removed
    // pattern in a comment explaining why the shared helper is used instead, and a
    // scanner that cannot tell code from prose would fail on the explanation itself.
    const source = read(path)
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");

    // A bare setTimeout re-scheduling a fetch is the hand-rolled pattern. It skips
    // pollDelay, and therefore skips pausing while the tab is hidden.
    const reschedules = source.match(/setTimeout\(\s*(poll|load|fetch|refresh)/g) ?? [];
    expect(reschedules).toHaveLength(0);

    // The positive half: stripping the loop is only correct if it was replaced by the
    // shared helper rather than dropped.
    expect(source).toMatch(/poll(MatchingStatus|PresentationReport)\(/);
  });
});

describe("pollPresentationReport", () => {
  it("exists so the pitch-deck page has a helper to delegate to", () => {
    // The page hand-rolled its loop because no helper covered this endpoint. Adding the
    // helper is what makes the delegation possible; without it the page has no
    // visibility-gated path to use.
    expect(API_SOURCE).toContain("export async function pollPresentationReport(");
  });

  it("treats both terminal states as done, not just success", () => {
    // The hand-rolled loop only rescheduled while "processing", which happens to be
    // correct — but a helper that stopped on "done" alone would spin forever on a
    // deck whose analysis failed.
    const start = API_SOURCE.indexOf("export async function pollPresentationReport(");
    const body = API_SOURCE.slice(start, start + 900);
    expect(body).toContain('!== "processing"');
  });
});
