"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Brain, ChevronDown } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { DataRow, DataRowList } from "@/components/common/DataRow";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ListSkeleton } from "@/components/common/Skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  fetchInterviewDefinitionAttempts,
  fetchMyInterviewDefinitions,
  type InterviewDefinitionAttempt,
} from "@/lib/api";
import { cn } from "@/lib/utils";

/** Recruiter-facing interview templates.
 *
 * The backend for this has always been complete — create, list, per-definition
 * attempts, and scored reports — and `api.ts` already had every client function. There
 * was simply no page, and the sidebar pointed at `/recruiter/interviews`, which 404s.
 * So recruiters could not reach a finished feature. */
export default function RecruiterInterviewsPage() {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchMyInterviewDefinitions(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    "recruiter:definitions",
  );
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <Page>
      <PageHeader
        title="Interview templates"
        description="Publish a template once, then review every candidate's scored attempt against it."
      />

      {error && !data ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : !data ? (
        <ListSkeleton rows={3} />
      ) : data.length === 0 ? (
        <EmptyState
          icon={Brain}
          title="No interview templates yet"
          description="A template defines the role and its questions. Candidates attempt it on demand, and each attempt comes back scored with a full transcript."
        />
      ) : (
        <DataRowList>
          {data.map((definition) => {
            const open = expanded === definition.id;
            return (
              <div key={definition.id} className="space-y-2">
                <DataRow
                  title={definition.title}
                  subtitle={`${definition.role_title} · ${definition.question_count} questions${
                    definition.duration_minutes
                      ? ` · ${definition.duration_minutes} min`
                      : ""
                  }`}
                  meta={
                    <StatusBadge
                      status={definition.is_active ? "active" : "draft"}
                      label={definition.is_active ? "Published" : "Unpublished"}
                    />
                  }
                  actions={
                    <Button
                      size="sm"
                      variant="outline"
                      aria-expanded={open}
                      onClick={() => setExpanded(open ? null : definition.id)}
                    >
                      Attempts
                      <ChevronDown
                        aria-hidden
                        className={cn(
                          "size-3.5 transition-transform duration-(--animate-duration-fast)",
                          open && "rotate-180",
                        )}
                      />
                    </Button>
                  }
                />
                {open ? <AttemptList definitionId={definition.id} /> : null}
              </div>
            );
          })}
        </DataRowList>
      )}
    </Page>
  );
}

/** Attempts for one template. Fetched only when expanded — a recruiter with twenty
 * templates should not pay twenty requests to see the list. */
function AttemptList({ definitionId }: { definitionId: string }) {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchInterviewDefinitionAttempts(token, definitionId);
  }, [getToken, definitionId]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    `recruiter:attempts:${definitionId}`,
  );

  if (error && !data) {
    return (
      <SectionError
        message={error}
        onRetry={retry}
        retrying={loading}
        className="ml-4"
      />
    );
  }
  if (!data) return <ListSkeleton rows={2} />;
  if (data.length === 0) {
    return (
      <EmptyState
        title="No attempts yet"
        description="Candidates who take this interview will appear here with their scored report."
        className="ml-4"
      />
    );
  }

  return (
    <div className="ml-4 flex flex-col gap-2">
      {data.map((attempt) => (
        <AttemptRow key={attempt.session_id} attempt={attempt} />
      ))}
    </div>
  );
}

function AttemptRow({ attempt }: { attempt: InterviewDefinitionAttempt }) {
  return (
    <DataRow
      title={attempt.candidate_name ?? "Candidate"}
      subtitle={`Started ${new Date(attempt.started_at).toLocaleDateString()}`}
      meta={
        <>
          <StatusBadge status={attempt.status} />
          {/* An unfinished interview has no report to open, so say so rather than
 offering a link that would 404. */}
          {!attempt.has_report ? (
            <Badge
              variant="outline"
              className="font-normal text-muted-foreground"
            >
              No report yet
            </Badge>
          ) : null}
        </>
      }
      actions={
        attempt.has_report ? (
          <Button
            size="sm"
            variant="outline"
            render={<Link href={`/reports/interview/${attempt.session_id}`} />}
          >
            View report
          </Button>
        ) : null
      }
    />
  );
}
