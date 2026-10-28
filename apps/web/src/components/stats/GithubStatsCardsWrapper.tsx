"use client";

import { Section } from "@/components/common/Section";
import { GithubStatsCards } from "@/components/stats/GithubStatsCards";
import type { GithubSummary } from "@/lib/api";

interface GithubStatsCardsWrapperProps {
  summary: GithubSummary;
}

export function GithubStatsCardsWrapper({
  summary,
}: GithubStatsCardsWrapperProps) {
  return (
    <Section title="GitHub Stats">
      <GithubStatsCards summary={summary} />
    </Section>
  );
}
