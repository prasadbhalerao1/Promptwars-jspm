import { describe, expect, it } from "vitest";

import {
  ApiError,
  MAX_AUTO_RETRIES,
  isConnectionFailure,
  isRetryable,
  isRetryableStatus,
  retryDelayMs,
  userFacingMessage,
} from "./errors";

/** The retry policy is where a wrong answer costs the user real time.
 *
 * Every LLM failure used to arrive as an identical 503, so the client retried all of
 * them — including an exhausted provider quota, which cannot succeed no matter how long
 * you wait. Four retries with backoff against a billing failure is ~15 seconds of
 * spinner before showing an error that was knowable immediately.
 */
describe("isRetryable", () => {
  it("retries a rate limit", () => {
    expect(isRetryable(new ApiError(429, { code: "LLM_RATE_LIMITED", retryable: true }))).toBe(true);
  });

  it("does NOT retry an exhausted quota", () => {
    expect(
      isRetryable(new ApiError(402, { code: "LLM_QUOTA_EXHAUSTED", retryable: false })),
    ).toBe(false);
  });

  it("does NOT retry a missing API key", () => {
    expect(
      isRetryable(new ApiError(503, { code: "LLM_NOT_CONFIGURED", retryable: false })),
    ).toBe(false);
  });

  it("honours the server's retryable flag over the status code", () => {
    // 503 would be retryable by status alone; the server says otherwise and wins.
    expect(isRetryable(new ApiError(503, { retryable: false }))).toBe(false);
    // 400 would not be retryable by status alone.
    expect(isRetryable(new ApiError(400, { retryable: true }))).toBe(true);
  });

  it("recognizes non-retryable codes in a plain stringified error", () => {
    // Older call sites throw `new Error(...)` with the body stringified rather than
    // constructing an ApiError; the classification must still hold.
    expect(isRetryable(new Error("POST /career failed: 402 LLM_QUOTA_EXHAUSTED"))).toBe(false);
    expect(isRetryable(new Error("503 LLM_NOT_CONFIGURED"))).toBe(false);
  });

  it("retries a bare connection failure", () => {
    expect(isRetryable(new TypeError("Failed to fetch"))).toBe(true);
    expect(isRetryable(new Error("NetworkError when attempting to fetch resource"))).toBe(true);
  });

  it("does not retry a real 4xx/5xx that merely mentions fetch", () => {
    // The distinction that matters: a connection-level failure carries no status code,
    // a real server error does. Retrying a 500 forever hides a genuine bug.
    expect(isRetryable(new Error("GET /me failed: 500"))).toBe(false);
    expect(isRetryable(new Error("failed to fetch: 404"))).toBe(false);
  });

  it("retries a transient gateway error", () => {
    for (const status of [429, 502, 503, 504]) {
      expect(isRetryable(new Error(`GET /x failed: ${status}`))).toBe(true);
    }
  });

  it("does not retry an auth failure", () => {
    expect(isRetryable(new Error("GET /me failed: 401"))).toBe(false);
    expect(isRetryable(new Error("GET /admin failed: 403"))).toBe(false);
  });
});

describe("isRetryableStatus", () => {
  it("excludes 402, because payment-required never self-heals", () => {
    expect(isRetryableStatus(402)).toBe(false);
  });

  it("includes the transient gateway statuses", () => {
    expect(isRetryableStatus(429)).toBe(true);
    expect(isRetryableStatus(503)).toBe(true);
  });
});

describe("isConnectionFailure", () => {
  it("separates a dead connection from an API error", () => {
    expect(isConnectionFailure(new TypeError("Failed to fetch"))).toBe(true);
    expect(isConnectionFailure(new Error("GET /me failed: 500"))).toBe(false);
  });
});

describe("retryDelayMs", () => {
  it("backs off exponentially", () => {
    expect(retryDelayMs(0)).toBe(1000);
    expect(retryDelayMs(1)).toBe(2000);
    expect(retryDelayMs(2)).toBe(4000);
  });

  it("caps so a down API is not hammered", () => {
    expect(retryDelayMs(10)).toBe(8000);
    expect(retryDelayMs(100)).toBe(8000);
  });
});

describe("userFacingMessage", () => {
  it("tells the user that retrying will not help an exhausted quota", () => {
    const message = userFacingMessage(
      new ApiError(402, { code: "LLM_QUOTA_EXHAUSTED", retryable: false }),
    );
    expect(message).toMatch(/not help|administrator/i);
  });

  it("does not tell the user to try again when the key is missing", () => {
    const message = userFacingMessage(
      new ApiError(503, { code: "LLM_NOT_CONFIGURED", retryable: false }),
    );
    expect(message).toMatch(/administrator/i);
    expect(message).not.toMatch(/try again/i);
  });

  it("does suggest retrying for a genuinely transient failure", () => {
    expect(
      userFacingMessage(new ApiError(429, { code: "LLM_RATE_LIMITED", retryable: true })),
    ).toMatch(/clears|try again|busy/i);
  });

  it("falls back to the raw message when there is no known code", () => {
    expect(userFacingMessage(new Error("something specific broke"))).toBe(
      "something specific broke",
    );
  });
});

describe("ApiError", () => {
  it("derives retryability from the status when the server omits the flag", () => {
    expect(new ApiError(503, { detail: "x" }).retryable).toBe(true);
    expect(new ApiError(402, { detail: "x" }).retryable).toBe(false);
  });

  it("keeps the server's code for downstream messaging", () => {
    expect(new ApiError(402, { code: "LLM_QUOTA_EXHAUSTED" }).code).toBe("LLM_QUOTA_EXHAUSTED");
  });
});

describe("MAX_AUTO_RETRIES", () => {
  it("is shared rather than redeclared per call site", () => {
    expect(MAX_AUTO_RETRIES).toBeGreaterThan(0);
    expect(MAX_AUTO_RETRIES).toBeLessThanOrEqual(5);
  });
});
