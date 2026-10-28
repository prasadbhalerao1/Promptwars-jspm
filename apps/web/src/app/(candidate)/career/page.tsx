"use client";

import { CareerGuidance } from "@/components/CareerGuidance";
import { Page, PageHeader } from "@/components/common/PageHeader";

/** Career guidance: roadmap, suggested courses, and salary ranges.
 *
 * The redirect-to-sign-in effect this page used to run was a second auth gate on
 * top of the one `WorkspaceShell` already applies to every route in this group.
 * Two gates racing each other is how a signed-in user ends up bounced mid-load,
 * so this defers to the shell. */
export default function CareerPage() {
  return (
    <Page>
      <PageHeader
        title="Career guidance"
        description="A roadmap based on your verified skills, with the gaps that separate you from your target role."
      />
      <CareerGuidance />
    </Page>
  );
}
