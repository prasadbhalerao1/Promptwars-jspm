"use client";

import { useAuth } from "@/components/AuthProvider";
import Link from "next/link";
import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import { toast } from "sonner";

import { AchievementsGrid } from "@/components/achievements/AchievementsGrid";
import { BadgeGrid } from "@/components/BadgeGrid";
import { PageHeader } from "@/components/common/PageHeader";
import { Section } from "@/components/common/Section";
import { SectionError } from "@/components/common/SectionError";
import { CardSkeleton } from "@/components/common/Skeleton";
import { Skeleton } from "@/components/ui/skeleton";
import { EvidenceReceipt } from "@/components/EvidenceReceipt";
import { ProblemSolvingStats } from "@/components/ProblemSolvingStats";
import { TalentScorePanel } from "@/components/TalentScorePanel";
import { ProfileSidebar } from "@/components/profile/ProfileSidebar";
import { RepositoryGrid } from "@/components/repositories/RepositoryGrid";
import { SkillsSection } from "@/components/skills/SkillsSection";
import { StatsGrid } from "@/components/stats/StatsGrid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAsyncResource } from "@/hooks/useAsyncResource";
import {
  connectGithubUsername,
  fetchGithubOAuthUrl,
  fetchGithubSummary,
  fetchMyBadges,
  fetchMyLatestScore,
  fetchMyProfile,
  fetchMyScoreHistory,
  publishPortfolio,
  refreshStats,
  unpublishPortfolio,
  type CandidateProfileResponse,
} from "@/lib/api";

// Dynamically imported: recharts + framer-motion are heavy dependencies only needed
// once GitHub/Talent Score data has actually loaded — keeping them out of this page's
// initial JS bundle shortens time-to-interactive for everything above the fold
// (profile sidebar, connect-GitHub CTA) that doesn't depend on them. ssr: false since
// these only ever render after client-side data resolves, so there's nothing to
// server-render for them anyway.
const ContributionHeatmap = dynamic(
  () =>
    import("@/components/charts/ContributionHeatmap").then(
      (m) => m.ContributionHeatmap,
    ),
  {
    ssr: false,
    loading: () => <div className="h-32 animate-pulse rounded-md bg-muted" />,
  },
);
const LanguageChart = dynamic(
  () =>
    import("@/components/charts/LanguageChart").then((m) => m.LanguageChart),
  {
    ssr: false,
    loading: () => <div className="h-56 animate-pulse rounded-md bg-muted" />,
  },
);
const CommitActivityChart = dynamic(
  () =>
    import("@/components/charts/CommitActivityChart").then(
      (m) => m.CommitActivityChart,
    ),
  {
    ssr: false,
    loading: () => <div className="h-56 animate-pulse rounded-md bg-muted" />,
  },
);
const ScoreRadarChart = dynamic(
  () => import("@/components/ScoreRadarChart").then((m) => m.ScoreRadarChart),
  {
    ssr: false,
    loading: () => <div className="h-72 animate-pulse rounded-md bg-muted" />,
  },
);
const ScoreTrendLine = dynamic(
  () => import("@/components/ScoreTrendLine").then((m) => m.ScoreTrendLine),
  {
    ssr: false,
    loading: () => <div className="h-56 animate-pulse rounded-md bg-muted" />,
  },
);

type ActivitySource = "combined" | "github" | "leetcode";

const ACTIVITY_SOURCE_LABELS: Record<ActivitySource, string> = {
  combined: "GitHub + LeetCode",
  github: "GitHub",
  leetcode: "LeetCode",
};

/** Total plus longest/current daily streaks (UTC dates) for a set of activity days. */
function summarizeActivity(days: { date: string; count: number }[]) {
  const active = new Set(days.filter((d) => d.count > 0).map((d) => d.date));
  const total = days.reduce((acc, d) => acc + d.count, 0);
  const dayMs = 86_400_000;
  const sorted = [...active].sort();
  let longest = 0;
  let run = 0;
  let prev = 0;
  for (const date of sorted) {
    const t = Date.parse(date);
    run = prev && t - prev === dayMs ? run + 1 : 1;
    longest = Math.max(longest, run);
    prev = t;
  }
  // A streak still counts as current if today simply has no activity yet.
  const todayMs = Date.parse(new Date().toISOString().slice(0, 10));
  let cursor = active.has(new Date(todayMs).toISOString().slice(0, 10))
    ? todayMs
    : todayMs - dayMs;
  let current = 0;
  while (active.has(new Date(cursor).toISOString().slice(0, 10))) {
    current++;
    cursor -= dayMs;
  }
  return { total, longest, current };
}

export function CandidateDashboard() {
  const { getToken } = useAuth();
  const [refreshBusy, setRefreshBusy] = useState(false);

  // Two independent fetches, deliberately not one.
  //
  // This was a single `/me/dashboard` call fanned out into three synthetic resource
  // objects that all shared one `loading` flag — so the entire page waited on the
  // slowest part of the payload (the GitHub summary, which scans every snapshot) before
  // *anything* could render. That is the "connect GitHub, then stare at nothing"
  // symptom.
  //
  // Splitting on the cheap/expensive boundary lets the profile, score and badges paint
  // from indexed lookups while the GitHub aggregate is still in flight. Both fetchers
  // are memoized on the now-stable `getToken`, so they are issued in parallel on mount
  // rather than serialized.
  const coreFetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    // Parallel, not sequential: these are four independent indexed queries and awaiting
    // them one at a time would stack four round trips into the critical path.
    const [profile, latestScore, scoreHistory, badges] = await Promise.all([
      fetchMyProfile(token),
      fetchMyLatestScore(token),
      fetchMyScoreHistory(token),
      fetchMyBadges(token),
    ]);
    return { profile, latestScore, scoreHistory, badges };
  }, [getToken]);

  const githubFetcher = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("No session token");
    return fetchGithubSummary(token);
  }, [getToken]);

  // cacheKey enables stale-while-revalidate: navigating away from the dashboard and back
  // shows the last-loaded data instantly instead of re-paying the backend round-trip
  // (which includes the DB's cold-connection latency on the first query of a session).
  const coreResource = useAsyncResource(coreFetcher, "dashboard:core");
  const githubResource = useAsyncResource(githubFetcher, "dashboard:github");

  const profileResource = {
    data: coreResource.data?.profile ?? null,
    loading: coreResource.loading,
    error: coreResource.error,
    retry: coreResource.retry,
  };
  const talentResource = {
    data: coreResource.data
      ? {
          latestScore: coreResource.data.latestScore,
          scoreHistory: coreResource.data.scoreHistory,
          badges: coreResource.data.badges,
        }
      : null,
    loading: coreResource.loading,
    error: coreResource.error,
    retry: coreResource.retry,
  };

  // Optimistically-updatable local copy — publish/unpublish/refresh mutate this directly
  // via their own response payload rather than re-fetching the whole bundle.
  const [profile, setProfile] = useState<CandidateProfileResponse | null>(null);
  const [prevProfileData, setPrevProfileData] =
    useState<CandidateProfileResponse | null>(null);

  if (profileResource.data !== prevProfileData) {
    setPrevProfileData(profileResource.data);
    setProfile(profileResource.data);
  }

  async function handleTogglePublic(published: boolean) {
    if (!profile) return;
    const token = await getToken();
    if (!token) return;
    try {
      const updated = published
        ? await publishPortfolio(token)
        : await unpublishPortfolio(token);
      setProfile(updated);
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : `Failed to ${published ? "publish" : "unpublish"} portfolio`,
      );
    }
  }

  const [busyConnect, setBusyConnect] = useState(false);
  const [githubInput, setGithubInput] = useState("");

  async function handleConnectUsername() {
    if (!githubInput.trim()) return;
    setBusyConnect(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const updated = await connectGithubUsername(token, githubInput.trim());
      setProfile(updated);
      toast.success(
        "GitHub profile connected! Analyzing repositories in background...",
      );
      setGithubInput("");
      coreResource.retry();
      githubResource.retry();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Could not connect GitHub",
      );
    } finally {
      setBusyConnect(false);
    }
  }

  async function handleConnectGithub() {
    setBusyConnect(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const authorizeUrl = await fetchGithubOAuthUrl(token);
      window.location.href = authorizeUrl;
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : "Could not start GitHub connection",
      );
      setBusyConnect(false);
    }
  }

  async function handleRefresh() {
    const token = await getToken();
    if (!token) return;
    setRefreshBusy(true);
    try {
      const updated = await refreshStats(token);
      setProfile(updated);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to refresh stats",
      );
    } finally {
      setRefreshBusy(false);
    }
  }

  // The cooldown comes from the profile response rather than a local constant. It is
  // env-tunable on the backend (`STATS_REFRESH_COOLDOWN_MINUTES`), so a mirrored literal
  // here would enable the button early after any deployment that changed it, and the
  // refresh would come back 429.
  const refreshCooldownUntil = profile?.stats_refreshed_at
    ? new Date(
        new Date(profile.stats_refreshed_at).getTime() +
          profile.stats_refresh_cooldown_seconds * 1000,
      )
    : null;

  const githubStats = profile?.github_stats ?? null;
  const githubUsername = profile?.github_username ?? null;
  // Development Stats genuinely needs both resources — the charts read `github_stats`
  // off the profile and the totals off the GitHub summary — so this section alone waits
  // on the pair. Every other section below reads only the resource it actually needs.
  const devStatsLoading = profileResource.loading || githubResource.loading;
  const devStatsError = profileResource.error ?? githubResource.error;

  const hasLeetcode = Boolean(profile?.leetcode_stats?.submission_calendar);
  const [activitySource, setActivitySource] =
    useState<ActivitySource>("combined");
  const source: ActivitySource = hasLeetcode ? activitySource : "github";

  const leetcodeDays = useMemo(() => {
    const calendar = profile?.leetcode_stats?.submission_calendar;
    if (!calendar) return [];
    return Object.entries(calendar).map(([unixSec, count]) => ({
      date: new Date(Number(unixSec) * 1000).toISOString().slice(0, 10),
      count: Number(count),
    }));
  }, [profile?.leetcode_stats]);

  const activityDays = useMemo(() => {
    const githubDays = githubStats?.days ?? [];
    if (source === "github") return githubDays;
    if (source === "leetcode") return leetcodeDays;
    const map = new Map<string, number>();
    for (const d of [...githubDays, ...leetcodeDays]) {
      map.set(d.date, (map.get(d.date) ?? 0) + d.count);
    }
    return Array.from(map.entries()).map(([date, count]) => ({ date, count }));
  }, [source, githubStats?.days, leetcodeDays]);

  const activityTotals = useMemo(() => {
    // GitHub-only keeps the backend's figures; the other views derive theirs from the
    // days shown so the numbers always match the grid.
    if (source === "github" && githubStats) {
      return {
        total: githubStats.total_contributions,
        longest: githubStats.longest_streak,
        current: githubStats.current_streak,
      };
    }
    return summarizeActivity(activityDays);
  }, [source, githubStats, activityDays]);

  return (
    <div className="mx-auto w-full max-w-workspace px-4 py-5 md:px-6 md:py-6">
      <PageHeader
        title="Your talent profile"
        description="Your Talent Score, the evidence behind it, and the development activity it draws on."
      />
      <div className="grid grid-cols-1 gap-4 md:gap-5 lg:grid-cols-[280px_1fr] lg:items-start">
        {profileResource.loading && !profile ? (
          // Sized to the real ProfileSidebar so the two-column grid is laid out from the
          // first paint and nothing jumps sideways when the profile lands.
          <CardSkeleton className="h-105 w-full" />
        ) : profileResource.error && !profile ? (
          <SectionError
            message={profileResource.error}
            onRetry={profileResource.retry}
            retrying={profileResource.loading}
          />
        ) : profile ? (
          <ProfileSidebar
            profile={profile}
            onTogglePublic={handleTogglePublic}
            onRefresh={handleRefresh}
            refreshBusy={refreshBusy}
            refreshCooldownUntil={refreshCooldownUntil}
          />
        ) : null}

        <div className="min-w-0 space-y-4 md:space-y-5">
          {/* The Talent Score leads the page. It is the answer to "how strong am I",
              which is the question that brought the candidate here, and it is computed
              from resume + assessments + interviews - not only from GitHub. It used to
              render inside the GitHub branch below, so a candidate with a real score of
              82.0 but no GitHub connection saw nothing but a Connect button. */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-5">
            {talentResource.loading && !talentResource.data ? (
              <Card>
                <CardContent className="space-y-3 p-6">
                  {/* A skeleton, not an empty state: the score is loading, not absent. */}
                  <Skeleton className="h-8 w-24" />
                  <Skeleton className="h-3 w-40" />
                  <Skeleton className="h-3 w-32" />
                </CardContent>
              </Card>
            ) : talentResource.error && !talentResource.data ? (
              <SectionError
                message={talentResource.error}
                onRetry={talentResource.retry}
                retrying={talentResource.loading}
              />
            ) : !talentResource.data?.latestScore ? (
              <Card className="border-border bg-card text-foreground shadow-flat ">
                <CardHeader className="pb-3 border-b border-border">
                  <CardTitle className="text-section font-semibold text-foreground">
                    Connect evidence to get Talent Score
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-4">
                  <p className="mb-4 text-xs text-muted-foreground">
                    Connect GitHub and upload a resume to compute your first
                    Talent Score.
                  </p>
                  <Button
                    className="w-full"
                    render={<Link href="/profile/edit" />}
                  >
                    Get started
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* The score ships with its confidence, its age and the evidence
                    behind each sub-score. A bare number invites a decision it cannot
                    support. */}
                <TalentScorePanel score={talentResource.data.latestScore} />

                <Section title="Score shape">
                  <ScoreRadarChart
                    subScores={talentResource.data.latestScore.sub_scores}
                  />
                </Section>

                {/* Spans both columns: a time series reads badly in a half-width
                    cell, and as the third item in a 2-up grid it otherwise wrapped
                    into a lone narrow column with dead space beside it. */}
                <Section title="Score history" className="md:col-span-2">
                  <ScoreTrendLine history={talentResource.data.scoreHistory} />
                </Section>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Full width below the profile band: in the right-hand column these left the
          sidebar's column empty for the rest of the page. */}
      <div className="mt-4 space-y-4 md:mt-5 md:space-y-5">
        {/* The evidence behind that score, beside the badges it earned. */}
        {talentResource.data?.latestScore && (
          <div className="grid grid-cols-1 items-start gap-4 md:gap-5 lg:grid-cols-[3fr_2fr]">
            <EvidenceReceipt score={talentResource.data.latestScore} />
            <div className="space-y-4 md:space-y-5">
              <Section title="Badges">
                <BadgeGrid badges={talentResource.data.badges} />
              </Section>
              {githubResource.data ? (
                <>
                  <Section title="Skills Matrix">
                    <SkillsSection projects={githubResource.data.projects} />
                  </Section>
                  {/* Beside the evidence list rather than in a row of its own, so this
                        column is not left half empty next to the taller receipt. */}
                  <Section title="Languages">
                    <LanguageChart projects={githubResource.data.projects} />
                  </Section>
                </>
              ) : null}
            </div>
          </div>
        )}

        {devStatsLoading && !githubResource.data ? (
          // Matches the real Development Stats block (stat cards + two charts) so this
          // section reserves its final height instead of collapsing and pushing
          // everything below it down when the data arrives.
          <div className="space-y-4 md:space-y-5">
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <CardSkeleton className="h-24" />
              <CardSkeleton className="h-24" />
              <CardSkeleton className="h-24" />
              <CardSkeleton className="h-24" />
            </div>
            <CardSkeleton className="h-32" />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-5">
              <CardSkeleton className="h-56" />
              <CardSkeleton className="h-56" />
            </div>
          </div>
        ) : devStatsError && !githubResource.data ? (
          <SectionError
            message={devStatsError}
            onRetry={() => {
              profileResource.retry();
              githubResource.retry();
            }}
            retrying={devStatsLoading}
          />
        ) : !githubUsername || !githubStats || !githubResource.data ? (
          <Card className="border-border bg-card text-foreground shadow-flat">
            <CardContent className="p-8 flex flex-col items-center justify-center text-center space-y-4">
              <p className="text-sm text-muted-foreground font-medium max-w-md">
                Connect GitHub to unlock Development Stats, achievements, and
                repository analytics. Enter any GitHub username to analyze
                public repos, or authenticate via OAuth.
              </p>
              <div className="flex flex-col sm:flex-row items-center gap-2 w-full max-w-md justify-center">
                <Input
                  value={githubInput}
                  onChange={(e) => setGithubInput(e.target.value)}
                  placeholder="GitHub username (e.g. torvalds)"
                  className="max-w-64"
                />
                <Button
                  onClick={handleConnectUsername}
                  disabled={busyConnect || !githubInput.trim()}
                >
                  {busyConnect ? "Syncing..." : "Sync Profile"}
                </Button>
              </div>
              <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
                <span>or</span>
                <button
                  type="button"
                  onClick={handleConnectGithub}
                  disabled={busyConnect}
                  className="text-primary hover:underline font-medium"
                >
                  Authenticate with GitHub OAuth
                </button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Stats Grid */}
            <StatsGrid stats={githubStats} summary={githubResource.data} />

            {/* Row 1: Contribution Activity (Full-width) */}
            <Section
              title={`Contribution Activity (${ACTIVITY_SOURCE_LABELS[source]})`}
              action={
                hasLeetcode ? (
                  <Select
                    value={source}
                    onValueChange={(value) => {
                      if (value) setActivitySource(value as ActivitySource);
                    }}
                  >
                    <SelectTrigger
                      className="w-48"
                      aria-label="Activity source"
                    >
                      <SelectValue>
                        {(value: ActivitySource) =>
                          ACTIVITY_SOURCE_LABELS[value]
                        }
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {(
                        Object.keys(ACTIVITY_SOURCE_LABELS) as ActivitySource[]
                      ).map((key) => (
                        <SelectItem key={key} value={key}>
                          {ACTIVITY_SOURCE_LABELS[key]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : null
              }
            >
              <div className="mb-4 flex flex-wrap items-center gap-6 text-meta font-medium text-muted-foreground select-none">
                <span>
                  Total Activity:{" "}
                  <span className="font-semibold text-foreground">
                    {activityTotals.total}
                  </span>
                </span>
                <span>
                  Max Streak:{" "}
                  <span className="font-semibold text-foreground">
                    {activityTotals.longest}d
                  </span>
                </span>
                <span>
                  Current Streak:{" "}
                  <span className="font-semibold text-foreground">
                    {activityTotals.current}d
                  </span>
                </span>
              </div>
              <ContributionHeatmap days={activityDays} />
            </Section>

            {/* Languages sit beside the evidence receipt above when a score exists. */}
            {!talentResource.data?.latestScore && (
              <Section title="Languages">
                <LanguageChart projects={githubResource.data.projects} />
              </Section>
            )}
            <Section title="Commit Activity (weekly)">
              <CommitActivityChart
                weeklyCounts={githubStats.commit_activity_weekly}
              />
            </Section>

            {/* Row 6: Repository Analytics (Full Width) */}
            <Section title="Repository Analytics">
              <RepositoryGrid projects={githubResource.data.projects} />
            </Section>

            {/* Row 7: Problem Solving Stats (Full Width) */}
            {profile && (
              <ProblemSolvingStats
                leetcodeUsername={profile.leetcode_username}
                leetcodeStats={profile.leetcode_stats}
              />
            )}

            {/* Row 8: Achievements Portfolio (Full Width) */}
            <Section title="Achievements Portfolio">
              <AchievementsGrid
                githubStats={githubStats}
                githubSummary={githubResource.data}
                projects={githubResource.data.projects}
              />
            </Section>
          </>
        )}
      </div>
    </div>
  );
}
