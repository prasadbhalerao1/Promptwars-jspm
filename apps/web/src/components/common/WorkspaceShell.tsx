"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useCurrentUser } from "@/components/CurrentUserProvider";
import {
  ConnectionState,
  isConnectionError,
} from "@/components/common/ConnectionState";
import { SectionError } from "@/components/common/SectionError";
import { PageSkeleton } from "@/components/common/Skeleton";
import { WorkspaceNavList } from "@/components/common/WorkspaceNavList";
import { CommandPalette } from "@/components/common/CommandPalette";
import {
  ROLE_LABELS,
  type WorkspaceRole,
} from "@/components/common/workspaceNav";

export type {
  RoleCapability,
  WorkspaceRole,
} from "@/components/common/workspaceNav";

interface WorkspaceShellProps {
  /** Role this route is restricted to. Omit for routes serving every role (`/home`),
   * where the sidebar follows the viewer's own role and the only gate is
   * "signed in and onboarded". */
  role?: WorkspaceRole;
  children: React.ReactNode;
}

/** Sidebar + role gate shared by every authenticated route group.
 *
 * The sidebar renders immediately, before `GET /me` resolves. Previously each layout
 * returned a bare `<div>Loading…</div>` for the *whole* page until `me` arrived, so
 * every navigation between route groups blanked the entire chrome and repainted it —
 * the single biggest source of perceived jank in the app. Only `children` is gated
 * now: the nav is static markup that never depended on `me` in the first place, and
 * the role check still runs exactly as before.
 *
 * This gate is UX, not security, and nothing here should be mistaken for a second line
 * of defence: there is no Next.js middleware, and per `lib/api.ts` the frontend never
 * guards routes server-side — components call FastAPI directly with a bearer token.
 * Authorization is enforced solely by `require_role` on the API. (An earlier version of
 * this comment claimed the check also ran "server-side on every request", which read as
 * defence-in-depth that does not exist.)
 */
export function WorkspaceShell({ role, children }: WorkspaceShellProps) {
  const router = useRouter();
  const { me, isLoaded, isSignedIn, error, attempts, reload } =
    useCurrentUser();

  const viewerRole = me?.profile?.role as WorkspaceRole | undefined;
  // Before `me` resolves there is no role to look up, so fall back to the route's own
  // role (when it has one) to render a plausible sidebar rather than an empty rail.
  const navRole = viewerRole ?? role;

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }
    if (!me) return;
    if (me.onboarding_required || !me.profile) {
      router.replace("/onboarding");
      return;
    }
    // Only role-scoped routes redirect on mismatch; shared routes serve everyone.
    if (role && me.profile.role !== role) {
      router.replace("/home");
    }
  }, [isLoaded, isSignedIn, me, router, role]);

  const signedInAndOnboarded = isLoaded && isSignedIn && Boolean(me?.profile);
  const allowed = signedInAndOnboarded && (role ? viewerRole === role : true);
  // `me === undefined` means the fetch hasn't settled. Once it has, a non-matching role
  // means the effect above is mid-redirect, so keep showing the placeholder rather than
  // flashing content the user isn't entitled to.
  const settling = !isLoaded || me === undefined;

  return (
    <div className="flex flex-1">
      <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-60 shrink-0 flex-col gap-4 overflow-y-auto bg-sidebar px-3 py-5 shadow-flat md:flex">
        {navRole ? (
          <>
            <div className="flex items-center justify-between px-2">
              <h2 className="text-meta font-medium text-muted-foreground">
                {ROLE_LABELS[navRole]}
              </h2>
              {/* Surfaces the shortcut rather than leaving it undiscoverable. */}
              <kbd className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-meta text-muted-foreground">
                ⌘K
              </kbd>
            </div>
            <WorkspaceNavList role={navRole} />
            <CommandPalette role={navRole} />
          </>
        ) : null}
      </aside>

      <main className="min-w-0 flex-1">
        {error ? (
          // A bare "Failed to fetch" reads as a broken app when it usually just means
          // the API hasn't finished booting. Only genuine API errors get the red box.
          <div className="mx-auto w-full max-w-workspace px-4 py-8 md:px-8">
            {isConnectionError(error) ? (
              <ConnectionState
                onRetry={reload}
                retrying={false}
                attempts={attempts}
              />
            ) : (
              <SectionError message={error} onRetry={reload} retrying={false} />
            )}
          </div>
        ) : allowed ? (
          children
        ) : settling ? (
          <div className="mx-auto w-full max-w-workspace px-4 py-8 md:px-8">
            <PageSkeleton />
          </div>
        ) : null}
      </main>
    </div>
  );
}
