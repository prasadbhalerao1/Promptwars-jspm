"use client";

import { WorkspaceShell } from "@/components/common/WorkspaceShell";

export default function RecruiterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell role="recruiter">{children}</WorkspaceShell>;
}
