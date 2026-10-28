import { describe, expect, it, vi } from "vitest";

import { POLL_DEFAULTS, pollUntil } from "./api";

/** Polling had six independent implementations: four near-identical helpers in api.ts,
 * each re-declaring the same four constants, plus two hand-rolled `setTimeout` loops in
 * page components that used *different* intervals and skipped visibility-gating
 * entirely — so a backgrounded tab issued requests forever.
 *
 * These tests pin the behaviour every caller now shares.
 */
describe("pollUntil", () => {
  it("returns as soon as the work is done", async () => {
    const fetchOnce = vi
      .fn()
      .mockResolvedValueOnce({ status: "processing" })
      .mockResolvedValueOnce({ status: "done" });

    const result = await pollUntil(
      fetchOnce,
      (v: { status: string }) => v.status !== "processing",
      { status: "processing" },
      { intervalMs: 1, maxIntervalMs: 1, timeoutMs: 5000 },
    );

    expect(result.status).toBe("done");
    expect(fetchOnce).toHaveBeenCalledTimes(2);
  });

  it("reports progress through onUpdate so the UI is not frozen", async () => {
    const seen: string[] = [];
    await pollUntil(
      vi.fn()
        .mockResolvedValueOnce({ status: "processing", stage: "reading resume" })
        .mockResolvedValueOnce({ status: "done", stage: null }),
      (v: { status: string }) => v.status !== "processing",
      { status: "processing", stage: null },
      {
        intervalMs: 1,
        maxIntervalMs: 1,
        timeoutMs: 5000,
        onUpdate: (v: { stage: string | null }) => seen.push(v.stage ?? "none"),
      },
    );
    expect(seen).toEqual(["reading resume", "none"]);
  });

  it("tolerates transient failures rather than aborting a long wait", async () => {
    // One blip must not kill a three-minute poll.
    const fetchOnce = vi
      .fn()
      .mockRejectedValueOnce(new Error("Failed to fetch"))
      .mockRejectedValueOnce(new Error("Failed to fetch"))
      .mockResolvedValueOnce({ status: "done" });

    const result = await pollUntil(
      fetchOnce,
      (v: { status: string }) => v.status !== "processing",
      { status: "processing" },
      { intervalMs: 1, maxIntervalMs: 1, timeoutMs: 5000 },
    );
    expect(result.status).toBe("done");
    expect(fetchOnce).toHaveBeenCalledTimes(3);
  });

  it("gives up once failures persist, so a dead endpoint surfaces", async () => {
    const fetchOnce = vi.fn().mockRejectedValue(new Error("Failed to fetch"));

    await expect(
      pollUntil(fetchOnce, () => true, { status: "processing" }, {
        intervalMs: 1,
        maxIntervalMs: 1,
        timeoutMs: 5000,
      }),
    ).rejects.toThrow("Failed to fetch");

    expect(fetchOnce).toHaveBeenCalledTimes(POLL_DEFAULTS.maxConsecutiveErrors);
  });

  it("resets the error budget after a success", async () => {
    // Four failures, a success, then four more must NOT trip the five-strike limit.
    const fetchOnce = vi.fn();
    for (let i = 0; i < 4; i++) fetchOnce.mockRejectedValueOnce(new Error("blip"));
    fetchOnce.mockResolvedValueOnce({ status: "processing" });
    for (let i = 0; i < 4; i++) fetchOnce.mockRejectedValueOnce(new Error("blip"));
    fetchOnce.mockResolvedValueOnce({ status: "done" });

    const result = await pollUntil(
      fetchOnce,
      (v: { status: string }) => v.status !== "processing",
      { status: "processing" },
      { intervalMs: 1, maxIntervalMs: 1, timeoutMs: 5000 },
    );
    expect(result.status).toBe("done");
  });

  it("returns the last value seen on timeout rather than throwing", async () => {
    // The caller must be able to render a "still working" state; a throw here would
    // surface as an error for work that is merely slow.
    const result = await pollUntil(
      vi.fn().mockResolvedValue({ status: "processing" }),
      (v: { status: string }) => v.status !== "processing",
      { status: "processing" },
      { intervalMs: 1, maxIntervalMs: 1, timeoutMs: 30 },
    );
    expect(result.status).toBe("processing");
  });

  it("stops immediately when the caller aborts", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchOnce = vi.fn().mockResolvedValue({ status: "processing" });

    const result = await pollUntil(fetchOnce, () => false, { status: "aborted" }, {
      intervalMs: 1,
      timeoutMs: 5000,
      signal: controller.signal,
    });

    expect(result.status).toBe("aborted");
    expect(fetchOnce).not.toHaveBeenCalled();
  });

  it("backs off between attempts instead of hammering at a fixed rate", async () => {
    const timestamps: number[] = [];
    await pollUntil(
      vi.fn().mockImplementation(async () => {
        timestamps.push(Date.now());
        return { status: "processing" };
      }),
      (v: { status: string }) => v.status !== "processing",
      { status: "processing" },
      { intervalMs: 10, maxIntervalMs: 100, timeoutMs: 120 },
    );

    expect(timestamps.length).toBeGreaterThanOrEqual(3);
    const first = timestamps[1] - timestamps[0];
    const later = timestamps[timestamps.length - 1] - timestamps[timestamps.length - 2];
    // Later gaps must be strictly longer — that is what backoff means.
    expect(later).toBeGreaterThan(first);
  });
});

describe("POLL_DEFAULTS", () => {
  it("exposes one definition of the polling policy", () => {
    // These were re-declared inside four separate helpers, and contradicted by two
    // hand-rolled loops. A single exported object is what makes them consistent.
    expect(POLL_DEFAULTS.intervalMs).toBe(2000);
    expect(POLL_DEFAULTS.maxIntervalMs).toBe(5000);
    expect(POLL_DEFAULTS.timeoutMs).toBe(180_000);
    expect(POLL_DEFAULTS.backoffFactor).toBeGreaterThan(1);
    expect(POLL_DEFAULTS.maxConsecutiveErrors).toBe(5);
  });

  it("allows enough time for a full GitHub crawl", () => {
    // The previous 60s ceiling resolved with status still "processing", and the caller
    // rendered a stale profile only a hard refresh would clear.
    expect(POLL_DEFAULTS.timeoutMs).toBeGreaterThanOrEqual(120_000);
  });
});
