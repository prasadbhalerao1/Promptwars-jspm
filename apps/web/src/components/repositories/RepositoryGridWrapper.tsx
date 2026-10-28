"use client";

import { Section } from "@/components/common/Section";
import { RepositoryGrid } from "@/components/repositories/RepositoryGrid";
import type { GithubProjectSummary } from "@/lib/api";

interface RepositoryGridWrapperProps {
  projects: GithubProjectSummary[];
}

export function RepositoryGridWrapper({
  projects,
}: RepositoryGridWrapperProps) {
  return (
    <Section title="Repository Analytics">
      <RepositoryGrid projects={projects} />
    </Section>
  );
}
