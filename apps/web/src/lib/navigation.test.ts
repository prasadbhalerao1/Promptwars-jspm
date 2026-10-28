import { readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

import {
  ROLE_CAPABILITIES,
  hubCapabilitiesFor,
  isNavItemActive,
  navSectionsFor,
  type WorkspaceRole,
} from "@/components/common/workspaceNav";

/** Guards the navigation model.
 *
 * The sidebar and the `/home` hub were once two hand-maintained lists, and they drifted:
 * the recruiter sidebar carried a "Pipelines" entry pointing at the same href as
 * "My jobs" (so two rows highlighted at once and one could never be the active target),
 * and an earlier entry pointed at "/recruiter/interviews", a route that never existed.
 * Both classes of bug are checked here.
 */

const ROLES: WorkspaceRole[] = [
  "candidate",
  "recruiter",
  "organizer",
  "judge",
  "admin",
];

/** Every URL the App Router actually serves, derived from the route files on disk.
 * Route groups like `(candidate)` contribute nothing to the URL and are stripped. */
function routeUrls(): Set<string> {
  const appDir = join(__dirname, "..", "app");
  const urls = new Set<string>();

  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        walk(full);
      } else if (entry === "page.tsx") {
        const segments = relative(appDir, dir)
          .split(sep)
          .filter((s) => s && !(s.startsWith("(") && s.endsWith(")")));
        urls.add("/" + segments.join("/"));
      }
    }
  };
  walk(appDir);
  return urls;
}

const URLS = routeUrls();

describe("route inventory", () => {
  it("finds the app's routes", () => {
    // Guards the guard: if the walker broke, every href test below would pass vacuously.
    expect(URLS.size).toBeGreaterThan(20);
    expect(URLS.has("/home")).toBe(true);
  });
});

describe.each(ROLES)("%s navigation", (role) => {
  const caps = ROLE_CAPABILITIES[role];

  it("points every entry at a route that exists", () => {
    const missing = caps
      .map((c) => c.href)
      // Dynamic routes are entry points to a list, never linked with a bare param.
      .filter((href) => !URLS.has(href));
    expect(missing).toEqual([]);
  });

  it("has no duplicate hrefs", () => {
    // Two entries sharing an href means both highlight at once, and one of them can
    // never be the active target.
    const hrefs = caps.map((c) => c.href);
    expect(hrefs).toEqual([...new Set(hrefs)]);
  });

  it("has no duplicate labels", () => {
    const labels = caps.map((c) => c.label);
    expect(labels).toEqual([...new Set(labels)]);
  });

  it("keeps every capability reachable from the sidebar", () => {
    // A capability defined but not rendered in any section is dead configuration.
    const rendered = navSectionsFor(role).flatMap((s) => s.items.map((i) => i.href));
    expect([...rendered].sort()).toEqual([...caps.map((c) => c.href)].sort());
  });

  it("gives every hub card a description", () => {
    for (const cap of hubCapabilitiesFor(role)) {
      expect(cap.description, `${cap.href} needs a description`).toBeTruthy();
    }
  });

  it("does not offer /home as a hub card", () => {
    // It would link to the page the card sits on.
    expect(hubCapabilitiesFor(role).map((c) => c.href)).not.toContain("/home");
  });
});

describe("isNavItemActive", () => {
  it("matches exactly by default", () => {
    const item = { href: "/jobs" };
    expect(isNavItemActive(item, "/jobs")).toBe(true);
    // Without matchNested, /jobs and /jobs/new must not both highlight.
    expect(isNavItemActive(item, "/jobs/new")).toBe(false);
  });

  it("matches child routes when matchNested is set", () => {
    const item = { href: "/hackathons", matchNested: true };
    expect(isNavItemActive(item, "/hackathons/abc/join")).toBe(true);
  });

  it("does not treat a shared prefix as a child route", () => {
    // "/jobsearch" starts with "/jobs" but is not under it.
    const item = { href: "/jobs", matchNested: true };
    expect(isNavItemActive(item, "/jobsearch")).toBe(false);
  });
});
