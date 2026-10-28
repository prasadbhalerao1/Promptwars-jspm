"use client";

import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  useDraggable,
  useDroppable,
} from "@dnd-kit/core";
import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  APPLICATION_STAGE_LABELS,
  APPLICATION_STAGES,
  assignAssessment,
  type ApplicationStage,
  type ApplicationWithCandidateResponse,
} from "@/lib/api";

// Report link routing (QA finding "Recruiter #3"): prefer whichever report actually
// exists for this candidate — submission, then interview, then contribution — display
// only, doesn't affect card order.
function reportLinkFor(
  application: ApplicationWithCandidateResponse,
): { href: string; label: string } | null {
  if (application.latest_submission_id) {
    return {
      href: `/reports/submission/${application.latest_submission_id}`,
      label: "View Report",
    };
  }
  if (application.latest_interview_session_id) {
    return {
      href: `/reports/interview/${application.latest_interview_session_id}`,
      label: "View Report",
    };
  }
  if (application.latest_contribution_repo_full_name) {
    return {
      href: `/reports/contribution/${encodeURIComponent(application.latest_contribution_repo_full_name)}`,
      label: "View Report",
    };
  }
  return null;
}

const FRAUD_BADGE_LABEL: Record<
  NonNullable<ApplicationWithCandidateResponse["fraud_flag_status"]>,
  string
> = {
  raised: "Flag Raised",
  under_review: "Flag Under Review",
  upheld: "Fraud Flag Upheld",
};

function AssignAssessmentDialog({
  jobId,
  candidateId,
  onClose,
}: {
  jobId: string;
  candidateId: string;
  onClose: () => void;
}) {
  const { getToken } = useAuth();
  const [type, setType] = useState<"coding" | "mcq" | "project_analysis">(
    "coding",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleAssign() {
    setSubmitting(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      // Minimal default spec per type — the recruiter refines the real spec later via
      // the assessment's own edit flow (out of scope for this fix); this call just
      // proves the assignment loop end-to-end (QA finding "Recruiter #1").
      const spec =
        type === "mcq"
          ? { questions: [] }
          : type === "coding"
            ? { prompt: "", hidden_tests: [] }
            : {};
      await assignAssessment(token, { jobId, candidateId, type, spec });
      setDone(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to assign assessment",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <Card className="w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            Assign Assessment
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {done ? (
            <p className="text-sm text-success">
              Assessment assigned - the candidate will see it in their inbox.
            </p>
          ) : (
            <>
              <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                Type
                <select
                  className="select-control"
                  value={type}
                  onChange={(e) => setType(e.target.value as typeof type)}
                >
                  <option value="coding">Coding Challenge</option>
                  <option value="mcq">Multiple Choice Quiz</option>
                  <option value="project_analysis">Project Analysis</option>
                </select>
              </label>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button
                className="w-full"
                pending={submitting}
                onClick={handleAssign}
              >
                {submitting ? "Assigning…" : "Assign"}
              </Button>
            </>
          )}
          <Button variant="outline" className="w-full" onClick={onClose}>
            Close
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function CandidateCard({
  application,
  onAdvance,
}: {
  application: ApplicationWithCandidateResponse;
  onAdvance?: (nextStage: ApplicationStage) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: application.id,
    });
  const [assigning, setAssigning] = useState(false);
  const style = transform
    ? {
        transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
        zIndex: 10,
      }
    : undefined;
  const currentIndex = APPLICATION_STAGES.indexOf(application.stage);
  const nextStage = APPLICATION_STAGES[currentIndex + 1];
  const report = reportLinkFor(application);

  return (
    <Card
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={`p-3 bg-card shadow-flat cursor-grab active:cursor-grabbing hover:border-primary ${isDragging ? "opacity-50" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">
          {application.candidate_headline ??
            application.candidate_github_username ??
            "Candidate"}
        </p>
        {application.fraud_flag_status && (
          <Badge variant="destructive" className="text-meta shrink-0">
            {FRAUD_BADGE_LABEL[application.fraud_flag_status]}
          </Badge>
        )}
      </div>
      {application.candidate_overall_talent_score !== null && (
        <p className="text-xs text-success font-semibold mt-1">
          Talent Score: {application.candidate_overall_talent_score.toFixed(0)}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
        {onAdvance && nextStage && nextStage !== "rejected" && (
          <button
            onPointerDown={(e) => e.stopPropagation()}
            onClick={() => onAdvance(nextStage)}
            className="text-meta text-primary font-semibold hover:underline"
          >
            Advance to {APPLICATION_STAGE_LABELS[nextStage]} →
          </button>
        )}
        {report && (
          <Link
            href={report.href}
            onPointerDown={(e) => e.stopPropagation()}
            className="text-meta text-primary font-semibold hover:underline"
          >
            {report.label}
          </Link>
        )}
        <button
          onPointerDown={(e) => e.stopPropagation()}
          onClick={() => setAssigning(true)}
          className="text-meta text-primary font-semibold hover:underline"
        >
          Assign Assessment
        </button>
      </div>
      {assigning && (
        <AssignAssessmentDialog
          jobId={application.job_id}
          candidateId={application.candidate_id}
          onClose={() => setAssigning(false)}
        />
      )}
    </Card>
  );
}

function StageColumn({
  stage,
  applications,
  onAdvance,
}: {
  stage: ApplicationStage;
  applications: ApplicationWithCandidateResponse[];
  onAdvance: (applicationId: string, nextStage: ApplicationStage) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage });
  return (
    <Card
      ref={setNodeRef}
      className={`bg-card border-dashed ${isOver ? "border-primary" : ""}`}
    >
      <CardHeader className="p-3">
        <CardTitle className="text-sm font-semibold flex justify-between">
          <span>{APPLICATION_STAGE_LABELS[stage]}</span>
          <Badge variant="secondary" className="text-xs">
            {applications.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-2 space-y-2 min-h-16">
        {applications.map((a) => (
          <CandidateCard
            key={a.id}
            application={a}
            onAdvance={(next) => onAdvance(a.id, next)}
          />
        ))}
      </CardContent>
    </Card>
  );
}

export function KanbanBoard({
  applications,
  onStageChange,
}: {
  applications: ApplicationWithCandidateResponse[];
  onStageChange: (applicationId: string, nextStage: ApplicationStage) => void;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id));
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;
    const nextStage = over.id as ApplicationStage;
    const application = applications.find((a) => a.id === active.id);
    if (application && application.stage !== nextStage) {
      onStageChange(String(active.id), nextStage);
    }
  }

  const activeApplication = applications.find((a) => a.id === activeId);

  return (
    <DndContext onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
      <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
        {APPLICATION_STAGES.map((stage) => (
          <StageColumn
            key={stage}
            stage={stage}
            applications={applications.filter((a) => a.stage === stage)}
            onAdvance={onStageChange}
          />
        ))}
      </div>
      <DragOverlay>
        {activeApplication && <CandidateCard application={activeApplication} />}
      </DragOverlay>
    </DndContext>
  );
}
