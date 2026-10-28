"use client";

import { WorkspaceShell } from "@/components/common/WorkspaceShell";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell role="admin">{children}</WorkspaceShell>;
}
