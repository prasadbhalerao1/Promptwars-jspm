"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { Users } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import { Page, PageHeader } from "@/components/common/PageHeader";
import { SectionError } from "@/components/common/SectionError";
import { EmptyState } from "@/components/common/EmptyState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { CardListSkeleton } from "@/components/CardListSkeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchAdminUsers, updateUserRole, type Role } from "@/lib/api";

const ASSIGNABLE_ROLES: Role[] = [
  "candidate",
  "recruiter",
  "organizer",
  "judge",
  "admin",
];

/** What each role actually grants, so the operator is choosing a capability rather
 * than a label. Shown in the confirmation before the change is committed. */
const ROLE_EFFECT: Record<Role, string> = {
  candidate: "Can only see their own profile, applications and assessments.",
  recruiter: "Can search candidates, post jobs and move applicants through pipelines.",
  organizer: "Can create events, import teams and publish rankings.",
  judge: "Can score submissions in the evaluation queue.",
  admin: "Full access, including fraud review, the issuer registry and this page.",
};

export default function AdminUsersPage() {
  const { getToken } = useAuth();
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingChange, setPendingChange] = useState<{
    userId: string;
    name: string;
    from: Role;
    to: Role;
  } | null>(null);

  // Was a useEffect plus a near-identical duplicate `load()` that existed only to
  // re-read after a mutation; `retry()` covers both.
  const fetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchAdminUsers(token);
  }, [getToken]);

  const { data, error: loadError, loading, retry } = useAsyncResource(
    fetcher,
    "admin:users",
  );

  const users = data ?? [];
  const error = actionError ?? loadError;

  async function handleConfirmRoleChange() {
    if (!pendingChange) return;
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      await updateUserRole(token, pendingChange.userId, pendingChange.to);
      toast.success(`${pendingChange.name} is now ${pendingChange.to}`, {
        description: "The change is recorded in the audit log.",
      });
      retry();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to update role";
      setActionError(message);
      toast.error(message);
    }
  }

  return (
    <Page>
      <PageHeader
        title="Users"
        description="Adjust what each account can do. Every change is written to the audit log."
      />

      {error ? (
        <SectionError
          message={error}
          onRetry={actionError ? () => setActionError(null) : retry}
          retrying={loading}
          className="mb-4"
        />
      ) : null}
      {loading && !data ? <CardListSkeleton /> : null}

      {data && users.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No users yet"
          description="Accounts appear here once people sign up."
        />
      ) : null}

      {users.length > 0 && (
        <ul className="rounded-xl shadow-flat">
          {users.map((user) => {
            const name = user.full_name ?? user.email;
            return (
              <li
                key={user.id}
                className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 last:border-0"
              >
                <div className="min-w-0">
                  <p className="truncate text-body font-medium text-foreground">
                    {name}
                  </p>
                  {user.full_name ? (
                    <p className="truncate text-meta text-muted-foreground">
                      {user.email}
                    </p>
                  ) : null}
                </div>
                {/* A role change used to commit the moment the select changed, so
                    granting someone full admin was a single stray interaction with
                    no undo. It now states the effect and asks first. */}
                <Select
                  value={user.role}
                  onValueChange={(value) => {
                    const next = value as Role;
                    if (!next || next === user.role) return;
                    setPendingChange({
                      userId: user.id,
                      name,
                      from: user.role,
                      to: next,
                    });
                  }}
                >
                  <SelectTrigger
                    className="w-40 capitalize"
                    aria-label={`Role for ${name}`}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ASSIGNABLE_ROLES.map((r) => (
                      <SelectItem key={r} value={r} className="capitalize">
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </li>
            );
          })}
        </ul>
      )}

      <ConfirmDialog
        open={pendingChange !== null}
        onOpenChange={(open) => {
          if (!open) setPendingChange(null);
        }}
        title={`Change role to ${pendingChange?.to}?`}
        description={
          pendingChange ? (
            <>
              <span className="text-foreground">{pendingChange.name}</span> will
              change from {pendingChange.from} to {pendingChange.to}.{" "}
              {ROLE_EFFECT[pendingChange.to]}
            </>
          ) : null
        }
        confirmLabel={`Make ${pendingChange?.to}`}
        // Promoting to admin grants irreversible reach; everything else is a
        // routine reassignment and shouldn't be styled as an alarm.
        destructive={pendingChange?.to === "admin"}
        onConfirm={handleConfirmRoleChange}
      />
    </Page>
  );
}
