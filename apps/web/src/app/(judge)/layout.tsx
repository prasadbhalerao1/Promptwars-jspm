"use client";

import { WorkspaceShell } from "@/components/common/WorkspaceShell";

export default function JudgeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell role="judge">{children}</WorkspaceShell>;
}
