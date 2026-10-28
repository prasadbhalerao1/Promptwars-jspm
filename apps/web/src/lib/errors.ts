/** Shared classification of API failures, and the messages users actually see.
 *
 * Two problems this solves.
 *
 * First, retry decisions were made by pattern-matching status codes in the error string,
 * and every LLM failure used to arrive as the same 503 — so the client retried all of
 * them. Three are not retryable: an exhausted provider quota and a missing API key do not
 * resolve by waiting, and a retry loop against them just spends the user's time on a
 * guaranteed failure before showing the same error. The backend now sends a `code` and an
 * explicit `retryable` flag (see `_LLM_ERROR_RESPONSES` in services/api/main.py); this
 * module reads them, falling back to status-code heuristics for endpoints that predate
 * the typed responses.
 *
 * Second, `isTransient` existed in two files with subtly different implementations, and a
 * hand-inlined copy of the backoff formula lived in a third. One definition here.
 */

/** Structured error body the API sends for typed failures. */
export interface ApiErrorBody {
  detail?: string;
  code?: string;
  retryable?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly retryable: boolean;

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail ?? `Request failed: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    // Trust the server's own judgment when it supplies one; it knows whether the
    // underlying condition is self-healing. Otherwise fall back to the status code.
    this.retryable = body.retryable ?? isRetryableStatus(status);
  }
}

/** Statuses that clear on their own given a moment.
 *
 * 402 is deliberately absent: payment-required means an exhausted quota, which no amount
 * of waiting fixes. 503 is present because most 503s are a booting API — the LLM cases
 * that are *not* retryable send an explicit `retryable: false` that overrides this.
 */
export function isRetryableStatus(status: number): boolean {
  return status === 429 || status === 502 || status === 503 || status === 504;
}

/** Whether a caught error is worth retrying automatically. */
export function isRetryable(error: unknown): boolean {
  if (error instanceof ApiError) return error.retryable;

  const message = error instanceof Error ? error.message : String(error);

  // An explicit non-retryable code can reach us as a plain Error from older call sites
  // that stringify the response rather than constructing an ApiError.
  if (/LLM_QUOTA_EXHAUSTED|LLM_NOT_CONFIGURED/i.test(message)) return false;

  if (/\b(429|502|503|504)\b/.test(message) || /rate_limit_exceeded/i.test(message)) {
    return true;
  }

  // A connection-level failure carries no HTTP status; a real 4xx/5xx does. This is what
  // distinguishes "the API has not finished booting" from "the API answered with 500".
  return (
    /failed to fetch|networkerror|load failed/i.test(message) &&
    !/\b[45]\d\d\b/.test(message)
  );
}

/** Whether the failure is a connection problem rather than an API error.
 *
 * Kept distinct from {@link isRetryable} because the UI treats them differently: a
 * connection failure shows a "still connecting" state, an API error shows a red box.
 */
export function isConnectionFailure(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    /failed to fetch|networkerror|load failed/i.test(message) &&
    !/\b[45]\d\d\b/.test(message)
  );
}

/** Exponential backoff with a ceiling.
 *
 * Starts short so a boot-time miss recovers almost invisibly, then backs off so a
 * genuinely-down API is not hammered. Was duplicated as a hand-inlined expression in
 * CurrentUserProvider.
 */
export function retryDelayMs(attempt: number, { base = 1000, max = 8000 } = {}): number {
  return Math.min(base * 2 ** attempt, max);
}

export const MAX_AUTO_RETRIES = 4;

/** User-facing message for a failure, by error code.
 *
 * The generic "something went wrong" is actively harmful for these cases: a user told to
 * try again will keep trying against an exhausted quota, while the person who can fix it
 * never learns there is a problem.
 */
const MESSAGES_BY_CODE: Record<string, string> = {
  LLM_QUOTA_EXHAUSTED:
    "The AI provider account is out of credit, so AI features are paused. Retrying will not help - this needs an administrator to top up the account.",
  LLM_NOT_CONFIGURED:
    "AI features are not configured on this deployment. An administrator needs to add a provider API key.",
  LLM_RATE_LIMITED:
    "The AI provider is busy right now. This usually clears within a minute.",
  LLM_TIMEOUT:
    "The AI request took too long and was stopped. Trying again often works, especially for shorter inputs.",
  LLM_UNAVAILABLE:
    "The AI engine is temporarily unavailable. Please try again in a moment.",
  rate_limit_exceeded:
    "You are making requests faster than the limit allows. Please wait a moment.",
};

export function userFacingMessage(error: unknown): string {
  if (error instanceof ApiError && error.code && MESSAGES_BY_CODE[error.code]) {
    return MESSAGES_BY_CODE[error.code];
  }

  const message = error instanceof Error ? error.message : String(error);
  for (const [code, text] of Object.entries(MESSAGES_BY_CODE)) {
    if (message.includes(code)) return text;
  }

  if (isConnectionFailure(error)) {
    return "Could not reach the server. It may still be starting up.";
  }
  return message || "Something went wrong.";
}

/** Build an {@link ApiError} from a failed `fetch` Response.
 *
 * Reads the JSON body when there is one so `code` and `retryable` survive; falls back to
 * the status text for non-JSON error responses.
 */
export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    body = { detail: `${response.statusText || "Request failed"} (${response.status})` };
  }
  return new ApiError(response.status, body);
}
