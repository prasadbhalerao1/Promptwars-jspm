import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { PYODIDE_INDEX_URL, resolveBackendUrl } from "./env";

/** Environment-derived URLs, and the literals that used to stand in for them.
 *
 * `http://localhost:8000` was written out three times as a fallback across two different
 * env var names, and the Pyodide CDN URL was a bare literal — a CDN outage or a pinned
 * version bump broke every coding assessment with no deployment-level way to redirect it.
 */

function read(relativePath: string): string {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), "utf-8");
}

describe("resolveBackendUrl", () => {
  it("prefers the explicit value", () => {
    expect(resolveBackendUrl("https://api.example.com")).toBe("https://api.example.com");
  });

  it("falls back to the local default when unset", () => {
    expect(resolveBackendUrl(undefined)).toBe("http://localhost:8000");
    expect(resolveBackendUrl("")).toBe("http://localhost:8000");
  });

  it("strips a trailing slash so callers can always concatenate a path", () => {
    // Without this, `${API_URL}/candidates/me` produced a double slash against any
    // deployment whose env var happened to end in one.
    expect(resolveBackendUrl("https://api.example.com/")).toBe("https://api.example.com");
  });

  it("ignores a whitespace-only value rather than producing an empty base URL", () => {
    expect(resolveBackendUrl("   ")).toBe("http://localhost:8000");
  });
});

describe("the localhost fallback", () => {
  it.each([
    ["./api.ts", "API_URL"],
    ["../app/(public)/[username]/page.tsx", "BACKEND_URL"],
    ["../app/api/auth/github/callback/route.ts", "BACKEND_URL"],
  ])("%s imports the resolved base instead of repeating the literal", (path, symbol) => {
    // Not comment-stripped: a `//` line-comment regex also eats the `//` inside a URL
    // and inside `"@/lib/env"`, which is what made an earlier version of this test
    // report a false failure. The literal is what matters, and none of these files
    // mention it in prose.
    const source = read(path);

    expect(source).not.toContain("http://localhost:8000");
    // Call sites consume the already-resolved constant; only env.ts calls the resolver.
    expect(source).toMatch(new RegExp(`import \\{[^}]*${symbol}[^}]*\\} from "@/lib/env"`));
  });
});

describe("PYODIDE_INDEX_URL", () => {
  it("is overridable by environment", () => {
    // A hardcoded CDN URL means a jsdelivr outage takes down coding assessments with no
    // remedy short of a redeploy. Self-hosting the assets must be a config change.
    const source = read("./env.ts");
    expect(source).toContain("NEXT_PUBLIC_PYODIDE_INDEX_URL");
  });

  it("still defaults to the pinned CDN version", () => {
    // The version is pinned deliberately — Pyodide's stdlib assets must match the loader.
    expect(PYODIDE_INDEX_URL).toMatch(/pyodide\/v\d+\.\d+\.\d+\/full\/$/);
  });

  it("keeps its trailing slash, which Pyodide requires of indexURL", () => {
    expect(PYODIDE_INDEX_URL.endsWith("/")).toBe(true);
  });

  it("is no longer declared in pyodideRunner", () => {
    const source = read("./pyodideRunner.ts");
    expect(source).not.toContain("https://cdn.jsdelivr.net");
  });
});
