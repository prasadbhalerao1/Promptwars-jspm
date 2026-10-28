"use client";

import { AtsResumeBuilder } from "@/components/AtsResumeBuilder";
import { Page, PageHeader } from "@/components/common/PageHeader";

export default function ResumeBuilderPage() {
  return (
    // `wide` rather than the default workspace width: the editor and the live
    // resume preview sit side by side, and the preview is a fixed-geometry page
    // that shouldn't be squeezed.
    <Page width="wide">
      <PageHeader
        title="Resume builder"
        description="Build a one-page resume that parses cleanly in applicant tracking systems, and tailor it to a specific job description."
      />
      <AtsResumeBuilder />
    </Page>
  );
}
