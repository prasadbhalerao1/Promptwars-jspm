"use client";

// Doc/SRS/06 §9's `(admin)/fraud-review/page.tsx` — "review queue, evidence viewer,
// upheld/dismiss actions." Wired to `GET /admin/fraud-review-queue` (see
// .agents/decisions.md's Module 06 entry). Only `raised`/`under_review` flags show up
// here — once a human resolves one, it leaves this queue.

import { useCallback, useMemo } from "react";
import { ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { DataRow, DataRowList } from "@/components/common/DataRow";
import { EmptyState } from "@/components/common/EmptyState";
import { Page, PageHeader, SectionHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { ListSkeleton } from "@/components/common/Skeleton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { fetchFraudReviewQueue, type FraudReviewQueueEntry } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Confidence in the *signal*, not guilt. Muted rather than alarming: a high-confidence
 * detection is still only evidence until a human upholds it. */
const CONFIDENCE_TONE: Record<string, string> = {
  high: "text-warning",
  medium: "text-muted-foreground",
  low: "text-muted-foreground",
};

export default function AdminFraudQueuePage() {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchFraudReviewQueue(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(fetcher, "admin:fraud-queue");

  // Disputed flags have a candidate actively waiting on a decision, so they lead.
  const { disputed, rest } = useMemo(() => {
    const entries = data ?? [];
    return {
      disputed: entries.filter((entry) => entry.has_dispute),
      rest: entries.filter((entry) => !entry.has_dispute),
    };
  }, [data]);

  return (
    <Page>
      <PageHeader
        title="Fraud review"
        description="Audit certificate, plagiarism, duplicate-profile and AI-content signals. Nothing counts against a candidate until you uphold it."
      />

      {error && !data ? (
        <SectionError message={error} onRetry={retry} retrying={loading} />
      ) : !data ? (
        <ListSkeleton rows={5} />
      ) : data.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="Nothing awaiting review"
          description="Flags raised by the detection agents land here for a human decision. The queue is currently clear."
        />
      ) : (
        <div className="space-y-8">
          {disputed.length > 0 ? (
            <section>
              <SectionHeader
                title="Disputed"
                description="A candidate has contested these - they're waiting on your decision."
              />
              <DataRowList>
                {disputed.map((entry) => (
                  <FlagRow key={entry.flag.id} entry={entry} />
                ))}
              </DataRowList>
            </section>
          ) : null}

          {rest.length > 0 ? (
            <section>
              <SectionHeader
                title={disputed.length > 0 ? "Everything else" : "Awaiting review"}
                description={`${rest.length} ${rest.length === 1 ? "flag" : "flags"}`}
              />
              <DataRowList>
                {rest.map((entry) => (
                  <FlagRow key={entry.flag.id} entry={entry} />
                ))}
              </DataRowList>
            </section>
          ) : null}
        </div>
      )}
    </Page>
  );
}

function FlagRow({ entry }: { entry: FraudReviewQueueEntry }) {
  const { flag, candidate_headline, candidate_github_username, has_dispute } = entry;
  const confidence =
    typeof flag.evidence?.confidence_label === "string"
      ? flag.evidence.confidence_label
      : "low";
  const summary =
    typeof flag.evidence?.report_summary === "string"
      ? flag.evidence.report_summary
      : null;

  return (
    <DataRow
      href={`/fraud-review/${flag.id}`}
      title={candidate_headline ?? candidate_github_username ?? "Unknown candidate"}
      subtitle={summary ?? flag.flag_type.replace(/_/g, " ")}
      meta={
        <>
          {has_dispute ? (
            <Badge variant="outline" className="font-normal text-warning">
              Disputed
            </Badge>
          ) : null}
          <Badge
            variant="outline"
            className={cn("font-normal", CONFIDENCE_TONE[confidence] ?? "")}
          >
            {confidence} confidence
          </Badge>
          <StatusBadge status={flag.status} />
        </>
      }
    />
  );
}
