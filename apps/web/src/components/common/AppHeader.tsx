"use client";

import Link from "next/link";
import { ExternalLink, Flag, FolderGit2, LogOut, Settings, User as UserIcon } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { MobileNav } from "@/components/common/MobileNav";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ROLE_LABELS,
  type WorkspaceRole,
} from "@/components/common/workspaceNav";

/** Global header: brand, mobile nav trigger, and the account menu.
 *
 * Extracted from the root layout so the layout stays declarative, and so the mobile
 * nav trigger can live beside the brand — the sidebar has no trigger of its own. */
export function AppHeader() {
  const { isSignedIn, logout } = useAuth();
  const { me } = useCurrentUser();
  const profile = me?.profile;
  const role = profile?.role as WorkspaceRole | undefined;

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between gap-3 bg-background/85 px-4 shadow-flat backdrop-blur-md md:px-6">
      <div className="flex min-w-0 items-center gap-2">
        {isSignedIn && role ? <MobileNav role={role} /> : null}
        <Link
          href={isSignedIn ? "/home" : "/"}
          className="flex items-center gap-2 rounded-sm text-section font-semibold tracking-tight outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          {/* The mark is the only always-on use of the accent: it reads as the
 product's verification stamp rather than as decoration. */}
          <span aria-hidden className="size-2 rounded-full bg-primary" />
          TRACE
        </Link>
      </div>

      <div className="flex items-center gap-2">
        {!isSignedIn ? (
          <>
            <Button variant="ghost" size="sm" render={<Link href="/sign-in" />}>
              Sign in
            </Button>
            <Button size="sm" render={<Link href="/sign-up" />}>
              Sign up
            </Button>
          </>
        ) : (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="sm" className="gap-2">
                  <UserIcon className="size-4" />
                  <span className="hidden max-w-40 truncate sm:inline">
                    {profile?.full_name || profile?.email || "Account"}
                  </span>
                </Button>
              }
            />
            <DropdownMenuContent align="end" className="w-60">
              <div className="px-2 py-1.5">
                <p className="truncate text-body font-medium">
                  {profile?.full_name || "Signed in"}
                </p>
                <p className="truncate text-meta text-muted-foreground">
                  {profile?.email}
                </p>
                {role ? (
                  <p className="mt-1 text-meta text-muted-foreground">
                    {ROLE_LABELS[role]}
                  </p>
                ) : null}
              </div>
              <DropdownMenuSeparator />
              {role === "candidate" ? (
                <>
                  <DropdownMenuItem
                    render={
                      <Link
                        href={profile?.username ? `/${profile.username}` : "/profile/edit"}
                        target={profile?.username ? "_blank" : undefined}
                      />
                    }
                  >
                    <ExternalLink className="size-4" />
                    <span>View Public Portfolio</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem render={<Link href="/profile/edit" />}>
                    <FolderGit2 className="size-4" />
                    <span>Evidence & Connected Accounts</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem render={<Link href="/my-flags" />}>
                    <Flag className="size-4" />
                    <span>Disputes and Flags</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem render={<Link href="/profile/edit" />}>
                    <Settings className="size-4" />
                    <span>Account Settings</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              ) : (
                <>
                  <DropdownMenuItem render={<Link href="/home" />}>
                    <Settings className="size-4" />
                    <span>Account Settings</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              )}
              <DropdownMenuItem onClick={logout} variant="destructive">
                <LogOut className="size-4" />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  );
}
