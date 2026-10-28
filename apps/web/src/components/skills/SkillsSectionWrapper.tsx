"use client";

import { Section } from "@/components/common/Section";
import { SkillsSection } from "@/components/skills/SkillsSection";
import type { GithubProjectSummary } from "@/lib/api";

interface SkillsSectionWrapperProps {
  projects: GithubProjectSummary[];
}

export function SkillsSectionWrapper({ projects }: SkillsSectionWrapperProps) {
  return (
    <Section title="Skills">
      <SkillsSection projects={projects} />
    </Section>
  );
}
