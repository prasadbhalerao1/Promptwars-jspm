"use client";

import { CandidateDashboard } from "@/components/CandidateDashboard";

// Inside the (candidate) route group so it renders with the workspace sidebar. It
// previously lived at the app root and branched on `me.profile.role` to serve all five
// roles from one file — which meant the app's landing page had no navigation at all.
// /home is now the role-aware hub; this is purely the candidate's data view.
export default function CandidateDashboardPage() {
  return <CandidateDashboard />;
}
