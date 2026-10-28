"use client";

import { WorkspaceShell } from "@/components/common/WorkspaceShell";

// Route group for authenticated pages that every role can reach. No `role` prop, so
// WorkspaceShell gates on "signed in and onboarded" only and renders the sidebar for
// the *viewer's* role. Next resolves route groups to the same URL space, so a shared
// route like /home can only be declared once — it cannot live in all five role groups.
export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
