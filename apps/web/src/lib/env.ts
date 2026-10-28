/** Environment-derived configuration, resolved in one place.
 *
 * The backend base URL was resolved at three sites under two env var names, each with its
 * own `?? "http://localhost:8000"`. The two *names* are a real distinction and are kept:
 * `NEXT_PUBLIC_API_URL` is inlined into the browser bundle, while `BACKEND_URL` is
 * server-only and used by the SSR portfolio fetch and the OAuth callback route, which
 * must reach the API over the internal network (doc 00 §2.1's SSR carve-out). What was
 * duplicated is the *fallback and normalization*, and that lives here now.
 */

const LOCAL_BACKEND = "http://localhost:8000";

/** Normalize a backend base URL: trim, drop a trailing slash, fall back to local.
 *
 * The trailing-slash strip matters because every call site builds paths by template
 * concatenation (`${API_URL}/candidates/me`). A deployment whose env var ended in `/`
 * produced `//candidates/me`, which some proxies rewrite and others 404.
 */
export function resolveBackendUrl(value: string | undefined): string {
  const trimmed = value?.trim();
  if (!trimmed) return LOCAL_BACKEND;
  return trimmed.replace(/\/+$/, "");
}

/** Browser-facing API base. Inlined at build time, so it must be a literal member access
 * on `process.env` rather than a dynamic lookup. */
export const API_URL = resolveBackendUrl(process.env.NEXT_PUBLIC_API_URL);

/** Server-only API base, for SSR and route handlers. Never exposed to the browser. */
export const BACKEND_URL = resolveBackendUrl(process.env.BACKEND_URL);

/** Where Pyodide loads its runtime and stdlib assets from.
 *
 * Was a bare literal in `pyodideRunner.ts`. Coding assessments run candidate code
 * client-side and depend entirely on these assets, so a jsdelivr outage took the whole
 * feature down with no remedy short of a redeploy. Overridable now, which also allows
 * self-hosting the assets for deployments that cannot reach a public CDN.
 *
 * The version stays pinned: the loader and the stdlib assets are a matched pair, and
 * floating this to `latest` would break the runtime on any upstream release.
 */
export const PYODIDE_INDEX_URL =
  process.env.NEXT_PUBLIC_PYODIDE_INDEX_URL?.trim() ||
  "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
