"use client";

import { HomeHub } from "@/components/home/HomeHub";

// Landing page after sign-in, for all five roles. Renders inside a route group so it
// inherits the workspace sidebar — the previous landing page (/dashboard at the app
// root) had no navigation at all, which left every feature undiscoverable.
export default function HomePage() {
  return <HomeHub />;
}
