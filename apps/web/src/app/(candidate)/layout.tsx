"use client";

import { WorkspaceShell } from "@/components/common/WorkspaceShell";

export default function CandidateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell role="candidate">{children}</WorkspaceShell>;
}
