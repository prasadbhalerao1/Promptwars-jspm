"use client";

import { useCallback } from "react";
import { ScrollText } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import { fetchAuditLog } from "@/lib/api";

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toLocaleString();
}

function formatAction(action: string): string {
  return action
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export default function AdminAuditLogsPage() {
  const { getToken } = useAuth();

  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchAuditLog(token);
  }, [getToken]);

  const { data, error, loading, retry } = useAsyncResource(
    fetcher,
    "admin:audit-log",
  );
  const logs = data ?? [];

  return (
    <Page>
      <PageHeader
        title="Audit log"
        description="Every sensitive operation - role changes, flag decisions, dispute resolutions - appended here. Entries cannot be edited or deleted by anyone, including admins."
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

      {data && logs.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No activity recorded yet"
          description="Audit entries appear here as soon as anyone performs a sensitive operation."
        />
      ) : null}

      {logs.length > 0 && (
        // Was a stack of bordered cards inside another card, plus two sidebar
        // panels restating the same policy and citing an internal architecture
        // doc path at the operator. The policy now lives in the page description
        // and the records are a plain scannable list.
        <ul className="rounded-xl shadow-flat">
          {logs.map((log) => (
            <li
              key={log.id}
              className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-border px-4 py-3 last:border-0"
            >
              <div className="min-w-0">
                <p className="text-body font-medium text-foreground">
                  {formatAction(log.action)}
                </p>
                <p className="truncate text-meta text-muted-foreground">
                  {log.actor_user_id ? `by ${log.actor_user_id}` : "by system"}
                  {log.target_type
                    ? ` · ${log.target_type} ${log.target_id}`
                    : ""}
                </p>
              </div>
              <time
                dateTime={log.created_at}
                className="text-meta tabular-nums text-muted-foreground"
              >
                {formatTimestamp(log.created_at)}
              </time>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
