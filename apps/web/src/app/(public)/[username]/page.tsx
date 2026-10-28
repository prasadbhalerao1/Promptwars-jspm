// FR-5.2 — Public Candidate Portfolio (Bento Grid).
// Server-Side Rendered (SSR) for optimal Lighthouse SEO and instant first paint.
// Backed by real evidence, verified credentials, and observable proof of work.

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Calendar,
  CheckCircle2,
  Code2,
  ExternalLink,
  Flame,
  FolderGit2,
  GitBranch,
  GraduationCap,
  MapPin,
  ShieldCheck,
  Star,
  Terminal,
  Trophy,
} from "lucide-react";

import { CommitActivityChartLazy } from "@/components/charts/CommitActivityChartLazy";
import { ContributionHeatmap } from "@/components/charts/ContributionHeatmap";
import { LanguageChart } from "@/components/charts/LanguageChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchPublicPortfolio } from "@/lib/api";
import { BACKEND_URL } from "@/lib/env";

interface PageProps {
  params: Promise<{ username: string }>;
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { username } = await params;
  const portfolio = await fetchPublicPortfolio(BACKEND_URL, username);
  if (!portfolio) {
    return { title: "Profile not found - TRACE" };
  }
  const title = portfolio.headline
    ? `${portfolio.username} - ${portfolio.headline} | TRACE Portfolio`
    : `${portfolio.username} | TRACE Verified Portfolio`;
  return {
    title,
    description:
      portfolio.headline ??
      `${portfolio.username}'s verified talent profile, projects, and proof of work on TRACE.`,
  };
}

export default async function PublicPortfolioPage({ params }: PageProps) {
  const { username } = await params;
  const portfolio = await fetchPublicPortfolio(BACKEND_URL, username);

  if (!portfolio) {
    notFound();
  }

  const {
    headline,
    location,
    skills,
    experience,
    education,
    badges,
    overall_score,
    github_username,
    leetcode_username,
    github_stats,
    github_summary,
    leetcode_stats,
  } = portfolio;

  const projects = github_summary?.projects || [];
  const topProjects = projects.slice(0, 4);

  // Labelled from the score's own Evidence Confidence, never asserted.
  const available = portfolio.confidence_available_signals ?? null;
  const expected = portfolio.confidence_expected_signals ?? null;
  const ratio = available !== null && expected ? available / expected : null;
  const confidence =
    ratio === null
      ? { label: "Not scored yet", className: "text-muted-foreground" }
      : ratio >= 0.75
        ? { label: "High", className: "text-success" }
        : ratio >= 0.5
          ? { label: "Medium", className: "text-warning" }
          : { label: "Low", className: "text-destructive" };

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
        {/* Bento Grid Container */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-5">
          {/* ======================================================== */}
          {/* TILE 1: Hero & Identity (Span 8 Desktop, Span 12 Mobile) */}
          {/* ======================================================== */}
          <div className="col-span-12 lg:col-span-8 rounded-xl border border-border bg-card p-6 sm:p-8 shadow-flat flex flex-col justify-between relative overflow-hidden group">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  {/* Avatar Initials with online ring */}
                  <div className="relative flex size-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20 text-primary font-bold text-xl uppercase tracking-wider">
                    {portfolio.username.slice(0, 2)}
                    <span className="absolute -bottom-1 -right-1 size-3.5 rounded-full border-2 border-background bg-success" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-2xl sm:text-3xl font-heading font-bold tracking-tight text-foreground">
                        {portfolio.username}
                      </h1>
                      <Badge className="bg-primary/10 text-primary border-primary/20 gap-1 text-xs py-0.5">
                        <ShieldCheck className="size-3" /> Evidence-backed
                      </Badge>
                    </div>
                    {location && (
                      <p className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                        <MapPin className="size-3" /> {location}
                      </p>
                    )}
                  </div>
                </div>

                {/* Quick Action */}
                <div className="flex items-center gap-2">
                  {github_username && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5 text-xs"
                      render={
                        <Link
                          href={`https://github.com/${github_username}`}
                          target="_blank"
                          rel="noreferrer"
                        />
                      }
                    >
                      <GitBranch className="size-3.5" />
                      GitHub
                    </Button>
                  )}
                  {leetcode_username && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5 text-xs"
                      render={
                        <Link
                          href={`https://leetcode.com/${leetcode_username}`}
                          target="_blank"
                          rel="noreferrer"
                        />
                      }
                    >
                      <Code2 className="size-3.5" />
                      LeetCode
                    </Button>
                  )}
                </div>
              </div>

              {/* Headline & Bio */}
              <div className="pt-2">
                <p className="text-base sm:text-lg font-medium text-foreground leading-relaxed">
                  {headline || "Full-Stack Engineer & AI Systems Developer"}
                </p>
                <p className="text-xs text-muted-foreground mt-1 max-w-2xl leading-relaxed">
                  Talent profile on TRACE. The score is computed from GitHub
                  activity, LeetCode, assessments and credentials, and each part
                  links to the evidence behind it.
                </p>
              </div>
            </div>

            {/* Quick Proof Signals Footer */}
            <div className="pt-6 mt-6 border-t border-border/60 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              {github_stats && (
                <div className="flex items-center gap-1.5">
                  <Flame className="size-3.5 text-warning" />
                  <span>
                    <strong className="text-foreground font-mono font-semibold">
                      {github_stats.longest_streak}
                    </strong>{" "}
                    day streak
                  </span>
                </div>
              )}
              {github_stats && (
                <div className="flex items-center gap-1.5">
                  <GitBranch className="size-3.5 text-primary" />
                  <span>
                    <strong className="text-foreground font-mono font-semibold">
                      {github_stats.total_contributions}
                    </strong>{" "}
                    contributions
                  </span>
                </div>
              )}
              {leetcode_stats && (
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="size-3.5 text-success" />
                  <span>
                    <strong className="text-foreground font-mono font-semibold">
                      {leetcode_stats.total_solved}
                    </strong>{" "}
                    problems solved
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* ======================================================== */}
          {/* TILE 2: Talent Score & Standing (Span 4 Desktop)         */}
          {/* ======================================================== */}
          <div className="col-span-12 lg:col-span-4 rounded-xl border border-border bg-card p-6 shadow-flat flex flex-col justify-between">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Talent Intelligence
                </span>
                <Badge variant="outline" className="font-mono text-xs">
                  Registry v2.0
                </Badge>
              </div>

              <div>
                <div className="flex items-baseline gap-2">
                  {overall_score !== null ? (
                    <>
                      <span className="font-mono text-4xl sm:text-5xl font-bold tracking-tight text-foreground">
                        {overall_score.toFixed(1)}
                      </span>
                      <span className="text-sm font-medium text-muted-foreground">
                        / 100
                      </span>
                    </>
                  ) : (
                    <span className="text-sm text-muted-foreground font-mono">
                      Provisional Assessment
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Weighted composite of ten sub-scores. Missing signals are left
                  out and their weight redistributed, never counted as zero.
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-xl bg-muted/40 p-3 border border-border/60 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  Signals with evidence:
                </span>
                <span className="font-medium text-foreground">
                  {available !== null && expected
                    ? `${available} of ${expected}`
                    : "Not scored yet"}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  Evidence Confidence:
                </span>
                <span className={`font-medium ${confidence.className}`}>
                  {confidence.label}
                </span>
              </div>
            </div>
          </div>

          {/* ======================================================== */}
          {/* TILE 3: Activity Heatmap & Consistency (Span 12 Desktop) */}
          {/* ======================================================== */}
          {github_stats && (
            <div className="col-span-12 rounded-xl border border-border bg-card p-6 shadow-flat space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-heading font-semibold text-foreground flex items-center gap-2">
                    <Calendar className="size-4 text-primary" />
                    Engineering Activity & Consistency
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Observable commit activity and contribution cadence across
                    public repositories
                  </p>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-muted-foreground">
                    Total:{" "}
                    <strong className="text-foreground font-mono">
                      {github_stats.total_contributions}
                    </strong>
                  </span>
                  <span className="text-muted-foreground">
                    Current Streak:{" "}
                    <strong className="text-foreground font-mono">
                      {github_stats.current_streak} days
                    </strong>
                  </span>
                  <span className="text-muted-foreground">
                    Longest Streak:{" "}
                    <strong className="text-foreground font-mono">
                      {github_stats.longest_streak} days
                    </strong>
                  </span>
                </div>
              </div>

              <div className="overflow-x-auto pt-2">
                <ContributionHeatmap days={github_stats.days} />
              </div>
            </div>
          )}

          {/* ======================================================== */}
          {/* TILE 4: Featured Projects Showcase (Span 8 Desktop)      */}
          {/* ======================================================== */}
          <div className="col-span-12 lg:col-span-7 rounded-xl border border-border bg-card p-6 shadow-flat space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-heading font-semibold text-foreground flex items-center gap-2">
                  <FolderGit2 className="size-4 text-primary" />
                  Featured Repositories & Proof of Work
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Production codebases analyzed for correctness, architecture,
                  and maintainability
                </p>
              </div>
              <Badge variant="outline" className="text-xs font-mono">
                {projects.length} Repositories
              </Badge>
            </div>

            {topProjects.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                {topProjects.map((proj) => {
                  const repoName =
                    proj.repo_full_name.split("/")[1] || proj.repo_full_name;
                  const languages = proj.languages
                    ? Object.keys(proj.languages)
                    : [];
                  const primaryLanguage = languages[0];

                  return (
                    <div
                      key={proj.repo_full_name}
                      className="rounded-xl border border-border/80 bg-muted/20 p-4 flex flex-col justify-between hover:border-primary/50 transition-all group"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Link
                            href={`https://github.com/${proj.repo_full_name}`}
                            target="_blank"
                            rel="noreferrer"
                            className="font-mono text-sm font-semibold text-foreground group-hover:text-primary transition-colors flex items-center gap-1.5 truncate max-w-[180px]"
                          >
                            {repoName}
                            <ExternalLink className="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </Link>
                          {primaryLanguage && (
                            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-muted text-muted-foreground border border-border/60">
                              {primaryLanguage}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                          {proj.description || "No description on GitHub."}
                        </p>
                      </div>

                      <div className="pt-3 mt-3 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1">
                            <Star className="size-3" /> {proj.stars || 0}
                          </span>
                          <span className="flex items-center gap-1">
                            <GitBranch className="size-3" /> {proj.forks || 0}
                          </span>
                        </div>
                        <span className="font-mono text-xs text-muted-foreground">
                          From GitHub
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground italic py-6 text-center">
                No public repositories connected yet.
              </p>
            )}
          </div>

          {/* ======================================================== */}
          {/* TILE 5: Language Distribution & Skills (Span 5 Desktop)  */}
          {/* ======================================================== */}
          <div className="col-span-12 lg:col-span-5 rounded-xl border border-border bg-card p-6 shadow-flat flex flex-col justify-between space-y-4">
            <div>
              <h2 className="text-base font-heading font-semibold text-foreground flex items-center gap-2">
                <Code2 className="size-4 text-primary" />
                Technical Stack & Languages
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Share of code by language across public repositories, from
                GitHub
              </p>
            </div>

            {projects.length > 0 ? (
              <div className="py-2">
                <LanguageChart projects={projects} />
              </div>
            ) : (
              <p className="text-xs text-muted-foreground italic">
                No languages detected yet.
              </p>
            )}

            {/* Skills Pills */}
            {skills && skills.length > 0 && (
              <div className="pt-3 border-t border-border/60">
                <p className="text-xs font-medium text-foreground mb-2">
                  Corroborated Competencies:
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {skills.slice(0, 10).map((s, i) => (
                    <Badge
                      key={i}
                      variant="secondary"
                      className="text-xs py-0.5"
                    >
                      {s.name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ======================================================== */}
          {/* TILE 6: Algorithmic Problem Solving (Span 6 Desktop)     */}
          {/* ======================================================== */}
          {leetcode_stats && (
            <div className="col-span-12 lg:col-span-6 rounded-xl border border-border bg-card p-6 shadow-flat space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-heading font-semibold text-foreground flex items-center gap-2">
                    <Terminal className="size-4 text-warning" />
                    Problem Solving & Algorithms
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Corroborated LeetCode metrics and contest rating
                  </p>
                </div>
                <Badge variant="outline" className="text-xs font-mono">
                  @{leetcode_username}
                </Badge>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-xl bg-muted/40 p-3 border border-border/60 text-center">
                  <p className="text-xs text-muted-foreground">Easy</p>
                  <p className="font-mono text-xl font-bold text-success mt-1">
                    {leetcode_stats.easy_solved}
                  </p>
                </div>
                <div className="rounded-xl bg-muted/40 p-3 border border-border/60 text-center">
                  <p className="text-xs text-muted-foreground">Medium</p>
                  <p className="font-mono text-xl font-bold text-warning mt-1">
                    {leetcode_stats.medium_solved}
                  </p>
                </div>
                <div className="rounded-xl bg-muted/40 p-3 border border-border/60 text-center">
                  <p className="text-xs text-muted-foreground">Hard</p>
                  <p className="font-mono text-xl font-bold text-destructive mt-1">
                    {leetcode_stats.hard_solved}
                  </p>
                </div>
              </div>

              {leetcode_stats.latest_rating && (
                <div className="rounded-xl bg-muted/20 p-3 border border-border/60 flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Contest Rating:</span>
                  <span className="font-mono font-semibold text-foreground">
                    {leetcode_stats.latest_rating.toFixed(0)}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* ======================================================== */}
          {/* TILE 7: Weekly Velocity & Commit Rhythm (Span 6 Desktop) */}
          {/* ======================================================== */}
          {github_stats && (
            <div className="col-span-12 lg:col-span-6 rounded-xl border border-border bg-card p-6 shadow-flat space-y-4">
              <div>
                <h2 className="text-base font-heading font-semibold text-foreground flex items-center gap-2">
                  <Flame className="size-4 text-primary" />
                  Weekly Development Velocity
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  52-week commit cadence across verified repository snapshots
                </p>
              </div>
              <div className="py-2">
                <CommitActivityChartLazy
                  weeklyCounts={github_stats.commit_activity_weekly}
                />
              </div>
            </div>
          )}

          {/* ======================================================== */}
          {/* TILE 8: Verified Credentials & Badges (Span 12 Desktop)  */}
          {/* ======================================================== */}
          {badges && badges.length > 0 && (
            <div className="col-span-12 rounded-xl border border-border bg-card p-6 shadow-flat space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-heading font-semibold text-foreground flex items-center gap-2">
                    <Trophy className="size-4 text-warning" />
                    Verified Credentials & Competency Badges
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Skills corroborated by two or more independent signal
                    sources
                  </p>
                </div>
                <Badge variant="outline" className="text-xs">
                  {badges.length} Verified
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-2">
                {badges.map((b) => (
                  <div
                    key={b.id}
                    className="rounded-xl border border-success/20 bg-success/5 p-3 flex items-start gap-3"
                  >
                    <CheckCircle2 className="size-4 text-success shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <p className="text-xs font-semibold text-foreground">
                        {b.skill_name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Corroborated via {b.corroboration_sources.join(", ")}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ======================================================== */}
          {/* TILE 9: Professional Experience & Education (Span 12)    */}
          {/* ======================================================== */}
          {experience?.length || education?.length ? (
            <div className="col-span-12 rounded-xl border border-border bg-card p-6 shadow-flat space-y-6">
              <h2 className="text-base font-heading font-semibold text-foreground flex items-center gap-2">
                <GraduationCap className="size-4 text-primary" />
                Experience & Education
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {experience && experience.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Experience
                    </h3>
                    <div className="space-y-3">
                      {experience.map((entry, i) => {
                        const title = entry.title ? String(entry.title) : "";
                        const company = entry.company
                          ? String(entry.company)
                          : "";
                        const description = entry.description
                          ? String(entry.description)
                          : "";

                        return (
                          <div
                            key={i}
                            className="rounded-lg border border-border/60 p-3 bg-muted/20 space-y-1"
                          >
                            <p className="text-xs font-semibold text-foreground">
                              {title}
                              {company ? ` • ${company}` : ""}
                            </p>
                            {description && (
                              <p className="text-xs text-muted-foreground leading-relaxed">
                                {description}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {education && education.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Education
                    </h3>
                    <div className="space-y-3">
                      {education.map((entry, i) => {
                        const institution = entry.institution
                          ? String(entry.institution)
                          : "";
                        const degree = entry.degree ? String(entry.degree) : "";

                        return (
                          <div
                            key={i}
                            className="rounded-lg border border-border/60 p-3 bg-muted/20 space-y-1"
                          >
                            <p className="text-xs font-semibold text-foreground">
                              {institution}
                            </p>
                            {degree && (
                              <p className="text-xs text-muted-foreground">
                                {degree}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </main>
  );
}
