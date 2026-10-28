"use client";

import { WorkspaceShell } from "@/components/common/WorkspaceShell";

export default function OrganizerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell role="organizer">{children}</WorkspaceShell>;
}
