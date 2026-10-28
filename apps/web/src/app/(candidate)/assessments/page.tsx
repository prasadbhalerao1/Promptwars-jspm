"use client";

import { useCallback } from "react";
import { ClipboardList } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { EmptyState } from "@/components/common/EmptyState";
import { DataRow, DataRowList } from "@/components/common/DataRow";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { fetchMyAssessments, type AssessmentResponse } from "@/lib/api";

const ASSESSMENT_TYPE_LABELS: Record<AssessmentResponse["type"], string> = {
  coding: "Coding challenge",
  mcq: "Multiple choice quiz",
  project_analysis: "Project analysis",
};

export default function CandidateAssessmentsInboxPage() {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchMyAssessments(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    "candidate:assessments",
  );
  const assessments = data ?? [];

  return (
    <Page>
      <PageHeader
        title="Assessments"
        description="Challenges recruiters have assigned to you. Open one to start or continue."
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}
      {loading && !data ? <CardListSkeleton /> : null}

      {data && assessments.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="Nothing assigned yet"
          description="When a recruiter assigns you a coding challenge, quiz or project review, it will appear here."
        />
      ) : null}

      {assessments.length > 0 && (
        <DataRowList>
          {assessments.map((assessment) => (
            // The type was previously printed twice per row — once as the heading
            // and again as a badge beside it. It is the row's identity, so it is
            // the title, and the date carries the metadata slot.
            <DataRow
              key={assessment.id}
              href={`/assessments/${assessment.id}`}
              title={ASSESSMENT_TYPE_LABELS[assessment.type]}
              subtitle={`Assigned ${new Date(assessment.created_at).toLocaleDateString()}`}
            />
          ))}
        </DataRowList>
      )}
    </Page>
  );
}
