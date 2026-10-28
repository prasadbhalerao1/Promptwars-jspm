import { useCurrentUser } from "@/components/CurrentUserProvider";
import {
  Braces,
  Building2,
  Code2,
  GraduationCap,
  Link2,
  Mail,
  MapPin,
  Pencil,
  RefreshCw,
  Copy,
  Check,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { Card, CardContent } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import type { CandidateProfileResponse } from "@/lib/api";

interface ProfileSidebarProps {
  profile: CandidateProfileResponse;
  onTogglePublic: (published: boolean) => void | Promise<void>;
  onRefresh: () => void | Promise<void>;
  refreshBusy: boolean;
  refreshCooldownUntil: Date | null;
}

function useCountdown(target: Date | null): string | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!target) return;
    // Stop the moment the deadline passes. This interval used to keep firing at 1 Hz
    // forever once the countdown hit zero — re-rendering the whole sidebar every second
    // to display nothing, for as long as the page stayed open.
    if (target.getTime() <= Date.now()) return;

    const id = setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (target.getTime() - current <= 0) clearInterval(id);
    }, 1000);
    return () => clearInterval(id);
  }, [target]);

  return useMemo(() => {
    if (!target) return null;
    const ms = target.getTime() - now;
    if (ms <= 0) return null;
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
  }, [target, now]);
}

export function ProfileSidebar({
  profile,
  onTogglePublic,
  onRefresh,
  refreshBusy,
  refreshCooldownUntil,
}: ProfileSidebarProps) {
  const { me } = useCurrentUser();
  const user = me?.profile;
  const countdown = useCountdown(refreshCooldownUntil);
  const education = profile.education?.[0] as
    { institution?: string; degree?: string } | undefined;
  const [copied, setCopied] = useState(false);
  const github = profile.github_stats;

  const portfolioUrl = profile.username
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/${profile.username}`
    : null;

  function handleCopy() {
    if (!portfolioUrl) return;
    navigator.clipboard.writeText(portfolioUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="w-full"
    >
      <Card className="border-border/80 bg-card text-foreground shadow-flat hover:border-border transition-colors">
        <CardContent className="space-y-6 p-6">
          {/* Avatar and Edit Badge */}
          <div className="relative mx-auto h-28 w-28 group">
            <motion.div
              whileHover={{ scale: 1.05 }}
              transition={{ duration: 0.2 }}
              className="relative h-28 w-28 rounded-full ring-2 ring-ring group-hover:ring-ring transition-all duration-300 overflow-hidden"
            >
              {profile.github_username ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`https://github.com/${profile.github_username}.png`}
                  alt={profile.full_name ?? user?.full_name ?? "avatar"}
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-muted text-3xl font-semibold text-muted-foreground">
                  {(
                    profile.full_name ??
                    user?.full_name ??
                    profile.username ??
                    "?"
                  )
                    .slice(0, 1)
                    .toUpperCase()}
                </div>
              )}
            </motion.div>
            <Link
              href="/profile/edit"
              className="absolute -right-1 -bottom-1 flex h-8 w-8 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-card transition shadow-flat"
              title="Edit Profile"
            >
              <Pencil className="h-3.5 w-3.5" />
            </Link>
          </div>

          {/* User Name & Bio */}
          <div className="text-center space-y-1">
            <h2 className="font-heading text-lg font-bold text-foreground leading-snug">
              {profile.full_name ?? user?.full_name ?? "Candidate"}
            </h2>
            {/* A handle is an identifier, not a headline — mono reads it as one, and
                it no longer competes with the name above it. */}
            {profile.username && (
              <p className="font-mono text-meta text-muted-foreground">
                @{profile.username}
              </p>
            )}
            {github?.bio && (
              <p className="mt-2 text-xs text-muted-foreground leading-relaxed font-sans max-w-[220px] mx-auto">
                {github.bio}
              </p>
            )}
          </div>

          {/* Social Stats */}
          {(github?.followers !== undefined ||
            github?.following !== undefined) && (
            <div className="flex items-center justify-center gap-6 border-y border-border py-3 text-xs text-muted-foreground">
              <div>
                <span className="font-bold text-foreground">
                  {github?.followers ?? 0}
                </span>{" "}
                followers
              </div>
              <div className="h-3 w-px bg-muted" />
              <div>
                <span className="font-bold text-foreground">
                  {github?.following ?? 0}
                </span>{" "}
                following
              </div>
            </div>
          )}

          {/* Social Links */}
          <div className="flex items-center justify-center gap-4">
            {user?.email && (
              <motion.a
                whileHover={{ y: -2 }}
                href={`mailto:${user.email}`}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-card hover:bg-muted border border-border text-muted-foreground hover:text-foreground transition"
                title="Email"
              >
                <Mail className="h-4 w-4" />
              </motion.a>
            )}
            {profile.github_username && (
              <motion.a
                whileHover={{ y: -2 }}
                href={`https://github.com/${profile.github_username}`}
                target="_blank"
                rel="noreferrer"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-card hover:bg-muted border border-border text-muted-foreground hover:text-foreground transition"
                title={`@${profile.github_username} on GitHub`}
              >
                <Code2 className="h-4 w-4" />
              </motion.a>
            )}
            {profile.leetcode_username && (
              <motion.a
                whileHover={{ y: -2 }}
                href={`https://leetcode.com/${profile.leetcode_username}`}
                target="_blank"
                rel="noreferrer"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-card hover:bg-muted border border-border text-muted-foreground hover:text-foreground transition"
                title={`@${profile.leetcode_username} on LeetCode`}
              >
                <Braces className="h-4 w-4" />
              </motion.a>
            )}
            {github?.website_url && (
              <motion.a
                whileHover={{ y: -2 }}
                href={github.website_url}
                target="_blank"
                rel="noreferrer"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-card hover:bg-muted border border-border text-muted-foreground hover:text-foreground transition"
                title={github.website_url}
              >
                <Link2 className="h-4 w-4" />
              </motion.a>
            )}
          </div>

          {/* Location / Org / School */}
          <div className="space-y-3 pt-2 text-xs text-muted-foreground min-w-0 w-full">
            {profile.location && (
              <div className="flex items-center gap-3 min-w-0 w-full">
                <MapPin className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span
                  className="text-foreground font-medium truncate flex-1"
                  title={profile.location}
                >
                  {profile.location}
                </span>
              </div>
            )}
            {github?.company && (
              <div className="flex items-center gap-3 min-w-0 w-full">
                <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span
                  className="text-foreground truncate flex-1"
                  title={github.company}
                >
                  {github.company}
                </span>
              </div>
            )}
            {education?.institution && (
              <div className="flex items-start gap-3 min-w-0 w-full">
                <GraduationCap className="h-4 w-4 shrink-0 text-muted-foreground mt-0.5" />
                <div className="text-foreground leading-tight min-w-0 flex-1">
                  <p
                    className="font-medium truncate"
                    title={education.institution}
                  >
                    {education.institution}
                  </p>
                  {education.degree && (
                    <p
                      className="text-meta text-muted-foreground truncate mt-0.5"
                      title={education.degree}
                    >
                      {education.degree}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Visibility & Refresh Operations */}
          <div className="space-y-4 pt-4 border-t border-border">
            {profile.username ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Public Profile
                  </span>
                  <Switch
                    checked={profile.portfolio_published}
                    onCheckedChange={onTogglePublic}
                  />
                </div>
                {/* Unique portfolio link — always visible once username is claimed */}
                <div className="space-y-1.5">
                  <span className="text-xs text-muted-foreground">
                    Your portfolio link
                  </span>
                  <div className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5">
                    <Link
                      href={`/${profile.username}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 truncate text-xs font-mono text-primary hover:underline"
                    >
                      /{profile.username}
                    </Link>
                    <button
                      onClick={handleCopy}
                      className="shrink-0 rounded-md p-0.5 text-muted-foreground hover:text-foreground transition-colors"
                      title="Copy link"
                    >
                      {copied ? (
                        <Check className="h-3.5 w-3.5 text-success" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="space-y-1.5">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Portfolio Link
                </span>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Set a username to get your unique public link.
                </p>
                <Link
                  href="/profile/edit"
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary hover:underline transition-colors"
                >
                  <Pencil className="h-3 w-3" /> Set username in Profile
                </Link>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {countdown ? (
                  <>
                    Next Refresh{" "}
                    <span className="font-mono text-foreground font-semibold">
                      {countdown}
                    </span>
                  </>
                ) : (
                  "Sync Latest Stats"
                )}
              </span>
              <button
                onClick={() => onRefresh()}
                disabled={refreshBusy || countdown !== null}
                className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-30 disabled:pointer-events-none transition-all"
                title="Refresh stats"
              >
                <RefreshCw
                  className={`h-4 w-4 ${refreshBusy ? "animate-spin text-primary" : ""}`}
                />
              </button>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
