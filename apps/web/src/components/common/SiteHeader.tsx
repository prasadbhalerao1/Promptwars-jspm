"use client";

import { usePathname } from "next/navigation";

import { AppHeader } from "@/components/common/AppHeader";
import { LandingHeader } from "@/components/landing/LandingHeader";

/** Chooses between marketing chrome and app chrome.
 *
 * The root layout renders one header for every route, but `/` is a marketing page and
 * everything else is the product. Showing the signed-in account menu and mobile nav
 * trigger above a landing hero makes the page read as a dashboard someone forgot to log
 * out of; showing marketing anchors inside the workspace is worse.
 *
 * `usePathname` rather than a route-group layout because the landing page lives at the
 * root segment alongside the app's own routes, so there is no group boundary to hang a
 * second layout off. The project has no rewrites and no proxy file, so the pathname read
 * on the client always matches the one prerendered on the server.
 */
export function SiteHeader() {
  const pathname = usePathname();
  return pathname === "/" ? <LandingHeader /> : <AppHeader />;
}
