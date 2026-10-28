"use client";

import { useAuth } from "@/components/AuthProvider";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RoadmapTimeline } from "@/components/RoadmapTimeline";
import { SalaryRangeChart } from "@/components/SalaryRangeChart";
import {
  CAREER_GUIDANCE_ROLES,
  fetchCareerGuidance,
  type CareerGuidanceResponse,
} from "@/lib/api";

export function CareerGuidance() {
  const { getToken } = useAuth();
  const [targetRole, setTargetRole] = useState("");
  const [guidance, setGuidance] = useState<CareerGuidanceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Event-handler-triggered loads (role picker, refresh button) — safe to call
  // directly since it's never invoked from inside an effect body.
  const load = useCallback(
    async (role: string | undefined, refresh: boolean) => {
      setLoading(true);
      setError(null);
      try {
        const token = await getToken();
        if (!token) throw new Error("No session token");

        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(
            () =>
              reject(
                new Error(
                  "Career guidance request timed out after 60 seconds. Please try again.",
                ),
              ),
            60000,
          ),
        );

        const result = await Promise.race([
          fetchCareerGuidance(token, { targetRole: role, refresh }),
          timeoutPromise,
        ]);

        setGuidance(result);
        setTargetRole(result.target_role ?? role ?? "");
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load career guidance",
        );
      } finally {
        setLoading(false);
      }
    },
    [getToken],
  );

  // Initial mount fetch — inlined (rather than calling `load` above) so no setState
  // call happens synchronously within the effect body itself, same pattern as
  // CandidateDashboard.tsx's mount effect (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const token = await getToken();
        if (!token) throw new Error("No session token");

        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(
            () =>
              reject(
                new Error(
                  "Career guidance request timed out after 60 seconds. Please try again.",
                ),
              ),
            60000,
          ),
        );

        const result = await Promise.race([
          fetchCareerGuidance(token, {}),
          timeoutPromise,
        ]);

        if (cancelled) return;
        setGuidance(result);
        setTargetRole(result.target_role ?? "");
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load career guidance",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [getToken]);

  return (
    <div className="space-y-6">
      <Card>
        {/* Titled "Career Guidance", which now restated the page header directly
            above it. The card's actual job is the target-role control. */}
        <CardHeader>
          <CardTitle className="font-heading">Target role</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Select
              value={targetRole}
              onValueChange={(value) => load(value || undefined, false)}
            >
              <SelectTrigger id="target-role" className="w-64">
                <SelectValue placeholder="Auto-pick best-fit role" />
              </SelectTrigger>
              <SelectContent>
                {CAREER_GUIDANCE_ROLES.map((role) => (
                  <SelectItem key={role} value={role}>
                    {role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              pending={loading}
              onClick={() => load(targetRole, true)}
            >
              {loading ? "Refreshing…" : "Refresh"}
            </Button>
          </div>

          {error && (
            <div className="space-y-2">
              <p className="text-sm text-destructive">{error}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => load(targetRole, false)}
                disabled={loading}
              >
                Try Again
              </Button>
            </div>
          )}
          {loading && !guidance && (
            <p className="text-sm text-muted-foreground">
              Analyzing your skill gaps…
            </p>
          )}
        </CardContent>
      </Card>

      {guidance && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="font-heading">
                Skill Gaps{" "}
                {guidance.target_role ? `- ${guidance.target_role}` : ""}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {guidance.skill_gaps.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No significant gaps found for this role - your skill set
                  already covers it well.
                </p>
              ) : (
                <ol className="space-y-2">
                  {guidance.skill_gaps.map((gap) => (
                    <li
                      key={gap.skill}
                      className="flex items-center justify-between gap-4 text-sm"
                    >
                      <span className="flex items-center gap-2">
                        <Badge variant="outline">#{gap.priority}</Badge>
                        {gap.skill}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        match {(gap.similarity * 100).toFixed(0)}%
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading">Career Roadmap</CardTitle>
            </CardHeader>
            <CardContent>
              <RoadmapTimeline stages={guidance.roadmap.stages} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading">
                Recommended Courses
              </CardTitle>
            </CardHeader>
            <CardContent>
              {guidance.recommended_courses.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No matching courses for your current gaps.
                </p>
              ) : (
                <ul className="space-y-2">
                  {guidance.recommended_courses.map((course) => (
                    <li key={course.id} className="text-sm">
                      <a
                        href={course.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium text-primary hover:underline"
                      >
                        {course.title}
                      </a>{" "}
                      <span className="text-xs text-muted-foreground">
                        {course.provider}
                        {course.is_free ? " · free" : ""}
                        {course.estimated_hours
                          ? ` · ~${course.estimated_hours}h`
                          : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="font-heading">Salary Estimate</CardTitle>
            </CardHeader>
            <CardContent>
              {guidance.salary_estimate_low !== null &&
              guidance.salary_estimate_high !== null ? (
                <>
                  <SalaryRangeChart
                    low={guidance.salary_estimate_low}
                    high={guidance.salary_estimate_high}
                  />
                  {guidance.salary_rationale && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {guidance.salary_rationale}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {guidance.salary_rationale ??
                    "Salary estimate not available yet."}
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
