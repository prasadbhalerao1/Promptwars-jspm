"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/components/AuthProvider";
import { useCurrentUser } from "@/components/CurrentUserProvider";
import { calculateATSScore, type ATSScoreDetail } from "@/lib/atsScoring";
import {
  DocumentGenerationError,
  fetchMyProfile,
  generateResume,
  type GeneratedResumeContent,
} from "@/lib/api";

export type ResumeTemplateStyle = "apex" | "modern" | "creative" | "minimalist";

export interface ExperienceItem {
  id: string;
  company: string;
  role: string;
  location: string;
  dates: string;
  bullets: string[];
}

export interface ProjectItem {
  id: string;
  title: string;
  technologies: string;
  dates: string;
  bullets: string[];
}

export interface EducationItem {
  id: string;
  institution: string;
  degree: string;
  dates: string;
  gpa: string;
}

export interface ResumeData {
  fullName: string;
  roleTitle: string;
  phone: string;
  email: string;
  location: string;
  linkedin: string;
  github: string;
  portfolio: string;
  summary: string;
  skills: {
    languages: string;
    frameworks: string;
    tools: string;
    databases: string;
    cloud: string;
  };
  experience: ExperienceItem[];
  projects: ProjectItem[];
  education: EducationItem[];
}

/** An empty resume.
 *
 * This was previously a fully populated sample belonging to a named individual —
 * real-looking name, email, phone, LinkedIn/GitHub handles, employment history and
 * a CGPA. It was never replaced by the signed-in user's own data, so every
 * candidate opened the builder prefilled with a stranger's details, and "Export
 * PDF" would produce that as their resume. Starting empty is the only safe
 * default; the seeding effect below fills in what we already know about the user. */
const EMPTY_RESUME: ResumeData = {
  fullName: "",
  roleTitle: "",
  phone: "",
  email: "",
  location: "",
  linkedin: "",
  github: "",
  portfolio: "",
  summary: "",
  skills: {
    languages: "",
    frameworks: "",
    tools: "",
    databases: "",
    cloud: "",
  },
  experience: [],
  projects: [],
  education: [],
};

export function AtsResumeBuilder() {
  const { getToken } = useAuth();
  const { me } = useCurrentUser();
  const [data, setData] = useState<ResumeData>(EMPTY_RESUME);
  // A "has this already run" latch, not rendered state — a ref keeps it out of the
  // render cycle instead of triggering a cascading re-render from inside the effect.
  const seededRef = useRef(false);
  const [template, setTemplate] = useState<ResumeTemplateStyle>("apex");
  const [targetJd, setTargetJd] = useState("");
  const [isOptimizing, setIsOptimizing] = useState(false);
  // Surfaced in the UI: a failed or withheld generation must say so, not silently
  // leave the resume unchanged as if nothing had been clicked.
  const [aiError, setAiError] = useState<string | null>(null);
  const [factCheckFindings, setFactCheckFindings] = useState<string[] | null>(
    null,
  );
  const [activeTab, setActiveTab] = useState<
    "contact" | "skills" | "experience" | "projects" | "education"
  >("contact");
  const [showAtsDetails, setShowAtsDetails] = useState(false);

  // Fills in what the platform already knows about the signed-in candidate, so the
  // builder opens with their own details rather than a blank form. Runs once: after
  // that the user's edits own the document, and a late-arriving profile must not
  // overwrite something they have already typed.
  useEffect(() => {
    if (seededRef.current || !me?.profile) return;
    seededRef.current = true;

    const user = me.profile;
    setData((prev) => ({
      ...prev,
      fullName: user.full_name ?? "",
      email: user.email ?? "",
    }));

    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        if (!token) return;
        const profile = await fetchMyProfile(token);
        if (cancelled) return;
        setData((prev) => ({
          ...prev,
          roleTitle: prev.roleTitle || (profile.headline ?? ""),
          location: prev.location || (profile.location ?? ""),
          github: prev.github || (profile.github_username
            ? `github.com/${profile.github_username}`
            : ""),
          skills: {
            ...prev.skills,
            languages:
              prev.skills.languages ||
              (profile.skills ?? []).map((s) => s.name).join(", "),
          },
        }));
      } catch {
        // Seeding is a convenience. If the profile can't be read the user just
        // fills the form in themselves — never block the builder on it.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [me, getToken]);

  const atsScoreDetail = useMemo<ATSScoreDetail>(() => {
    const result = calculateATSScore(data);
    return result;
  }, [data]);

  const handlePrint = async () => {
    const element = document.getElementById("resume-document");
    if (!element) return;

    try {
      const html2pdfModule = await import("html2pdf.js");
      const html2pdf =
        html2pdfModule.default ||
        (html2pdfModule as unknown as () => {
          set: (opt: object) => {
            from: (el: HTMLElement) => { save: () => void };
          };
        });
      const options = {
        margin: 0,
        filename: `${data.fullName.replace(/\s+/g, "_")}_Resume.pdf`,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: {
          scale: 2,
          useCORS: true,
          logging: false,
          backgroundColor: "var(--popover)",
        },
        jsPDF: {
          orientation: "portrait",
          unit: "mm",
          format: "a4",
          compress: true,
        },
        pagebreak: { mode: ["avoid-all", "css", "legacy"] },
      };

      html2pdf().set(options).from(element).save();
    } catch (error) {
      console.error("PDF export failed:", error);
      window.print();
    }
  };

  // Calls the real generator (`POST /candidates/me/resume/generate`), which runs the
  // document-generation graph against the candidate's actual profile and passes the
  // output through the fact-check guardrail before returning it.
  //
  // This previously faked it: a 1200ms setTimeout that pasted a fixed "Results-driven
  // {role} with proven expertise in full-stack development…" summary and appended the
  // literal string "— demonstrated measurable impact aligned with JD requirements" to
  // every bullet, regardless of the JD or the candidate. It looked like AI tailoring and
  // was the same text for every user — worse than no feature, since a candidate could
  // send that to a real employer believing it had been personalized.
  const handleAiOptimize = async () => {
    if (!targetJd.trim()) {
      setAiError(
        "Paste a target job description first - tailoring needs something to tailor to.",
      );
      return;
    }
    setIsOptimizing(true);
    setAiError(null);
    setFactCheckFindings(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("No session token");
      const doc = await generateResume(token, targetJd);
      const content = doc.content as GeneratedResumeContent;

      setData((prev) => ({
        ...prev,
        summary: content.summary || prev.summary,
        roleTitle: content.headline || prev.roleTitle,
        // `skills` is deliberately left alone. The builder splits it into five curated
        // buckets (languages/frameworks/tools/databases/cloud) while the generator
        // returns one flat list, and there is no reliable way to bucket "Docker" or
        // "Postgres" back without guessing. Dumping the flat list into any single field
        // would silently destroy the candidate's own categorization.
        // Only replace experience when the generator actually returned some, so a sparse
        // profile can't blank out what the candidate typed by hand.
        experience: content.experience?.length
          ? content.experience.map((exp, i) => ({
              id: prev.experience[i]?.id ?? `exp-ai-${i}`,
              company: exp.company ?? prev.experience[i]?.company ?? "",
              role: exp.title ?? prev.experience[i]?.role ?? "",
              location: prev.experience[i]?.location ?? "",
              dates: exp.years ?? prev.experience[i]?.dates ?? "",
              bullets: exp.bullets?.length
                ? exp.bullets
                : (prev.experience[i]?.bullets ?? []),
            }))
          : prev.experience,
      }));

      // Surfaced rather than swallowed: the backend returns 200 with findings when the
      // guardrail passes but still flagged something worth the candidate's attention.
      if (doc.fact_check_findings?.length) {
        setFactCheckFindings(doc.fact_check_findings.map((f) => f.claim));
      }
    } catch (err) {
      if (err instanceof DocumentGenerationError && err.findings?.length) {
        // 422: the guardrail withheld the document because it contained claims the
        // profile does not support. Show exactly which ones.
        setAiError(
          "Generation was withheld - the draft contained unsupported claims:",
        );
        setFactCheckFindings(err.findings.map((f) => f.claim));
      } else {
        setAiError(err instanceof Error ? err.message : "AI tailoring failed");
      }
    } finally {
      setIsOptimizing(false);
    }
  };

  // Helper functions to add/remove dynamic fields
  const addExperience = () => {
    const newExp: ExperienceItem = {
      id: `exp-${Date.now()}`,
      company: "Tech Company Inc.",
      role: "Software Engineer",
      location: "San Francisco, CA",
      dates: "2024 - Present",
      bullets: [
        "Led implementation of core software features resulting in 25% performance improvement.",
      ],
    };
    setData((prev) => ({ ...prev, experience: [...prev.experience, newExp] }));
  };

  const removeExperience = (id: string) => {
    setData((prev) => ({
      ...prev,
      experience: prev.experience.filter((e) => e.id !== id),
    }));
  };

  const addProject = () => {
    const newProj: ProjectItem = {
      id: `proj-${Date.now()}`,
      title: "New AI Project",
      technologies: "Next.js, Python, PostgreSQL",
      dates: "2025",
      bullets: [
        "Designed and deployed full-stack web application with automated data pipelines.",
      ],
    };
    setData((prev) => ({ ...prev, projects: [...prev.projects, newProj] }));
  };

  const removeProject = (id: string) => {
    setData((prev) => ({
      ...prev,
      projects: prev.projects.filter((p) => p.id !== id),
    }));
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Was a bordered header bar carrying an invented product name ("CVInsight
          Engine") and a title written as marketing copy. The page owns the title
          now, so this is just the toolbar. */}
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowAtsDetails(!showAtsDetails)}
          aria-expanded={showAtsDetails}
        >
          <span className="text-muted-foreground">ATS readiness</span>
          {/* Was hard-coded `text-success`, so a 30/100 rendered in the same
              affirmative green as a 95/100. */}
          <span data-numeric className="font-medium tabular-nums">
            {atsScoreDetail.score}/100
          </span>
          <ChevronDown
            aria-hidden
            className={
              showAtsDetails
                ? "size-3.5 rotate-180 transition-transform"
                : "size-3.5 transition-transform"
            }
          />
        </Button>
        <Button onClick={handlePrint}>Export PDF</Button>
      </div>

      {/* ATS Score Details Panel */}
      {showAtsDetails && (
        <Card className="border-success/20 bg-success/10">
          <CardHeader>
            <CardTitle className="text-sm font-semibold text-success">
              ATS Score Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              <div className="bg-card p-2.5 rounded-md border border-success/20">
                <div className="font-bold text-success">
                  {atsScoreDetail.breakdown.parsing.score}
                </div>
                <div className="text-muted-foreground text-[11px]">Parsing</div>
              </div>
              <div className="bg-card p-2.5 rounded-md border border-success/20">
                <div className="font-bold text-success">
                  {atsScoreDetail.breakdown.contact.score}
                </div>
                <div className="text-muted-foreground text-[11px]">Contact</div>
              </div>
              <div className="bg-card p-2.5 rounded-md border border-success/20">
                <div className="font-bold text-success">
                  {atsScoreDetail.breakdown.keywords.score}
                </div>
                <div className="text-muted-foreground text-[11px]">
                  Keywords
                </div>
              </div>
              <div className="bg-card p-2.5 rounded-md border border-success/20">
                <div className="font-bold text-success">
                  {atsScoreDetail.breakdown.formatting.score}
                </div>
                <div className="text-muted-foreground text-[11px]">Format</div>
              </div>
              <div className="bg-card p-2.5 rounded-md border border-success/20">
                <div className="font-bold text-success">
                  {atsScoreDetail.breakdown.content.score}
                </div>
                <div className="text-muted-foreground text-[11px]">Content</div>
              </div>
            </div>

            <div className="space-y-2 bg-card p-2.5 rounded-md border border-success/20">
              <div className="font-semibold text-success">Issues Found:</div>
              {atsScoreDetail.breakdown.parsing.issues.length > 0 && (
                <div>
                  <div className="font-medium text-success mb-1">Parsing:</div>
                  <ul className="space-y-0.5 text-muted-foreground list-disc pl-4">
                    {atsScoreDetail.breakdown.parsing.issues.map((issue, i) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              {atsScoreDetail.breakdown.contact.issues.length > 0 && (
                <div>
                  <div className="font-medium text-success mb-1">
                    Contact Info:
                  </div>
                  <ul className="space-y-0.5 text-muted-foreground list-disc pl-4">
                    {atsScoreDetail.breakdown.contact.issues.map((issue, i) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              {atsScoreDetail.breakdown.keywords.issues.length > 0 && (
                <div>
                  <div className="font-medium text-success mb-1">Keywords:</div>
                  <ul className="space-y-0.5 text-muted-foreground list-disc pl-4">
                    {atsScoreDetail.breakdown.keywords.issues.map(
                      (issue, i) => (
                        <li key={i}>{issue}</li>
                      ),
                    )}
                  </ul>
                </div>
              )}
              {atsScoreDetail.breakdown.formatting.issues.length > 0 && (
                <div>
                  <div className="font-medium text-success mb-1">
                    Formatting:
                  </div>
                  <ul className="space-y-0.5 text-muted-foreground list-disc pl-4">
                    {atsScoreDetail.breakdown.formatting.issues.map(
                      (issue, i) => (
                        <li key={i}>{issue}</li>
                      ),
                    )}
                  </ul>
                </div>
              )}
              {atsScoreDetail.breakdown.content.issues.length > 0 && (
                <div>
                  <div className="font-medium text-success mb-1">Content:</div>
                  <ul className="space-y-0.5 text-muted-foreground list-disc pl-4">
                    {atsScoreDetail.breakdown.content.issues.map((issue, i) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
              {Object.values(atsScoreDetail.breakdown).every(
                (b) => b.issues.length === 0,
              ) && (
                <p className="flex items-center gap-1.5 text-success">
                  <Check aria-hidden className="size-3.5" />
                  No issues detected
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Template Switcher Buttons */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 print:hidden">
        <button
          type="button"
          onClick={() => setTemplate("apex")}
          aria-pressed={template === "apex"}
          className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
            template === "apex"
              ? "border-primary bg-primary/10 ring-2 ring-ring"
              : "border-border bg-card hover:border-primary/50"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-foreground">
              Apex
            </span>
            {template === "apex" && (
              <Badge variant="secondary" className="text-[10px]">
                Active
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            Universal 1-column LaTeX format. Built for FAANG & MNC placements.
          </p>
        </button>

        <button
          type="button"
          onClick={() => setTemplate("modern")}
          aria-pressed={template === "modern"}
          className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
            template === "modern"
              ? "border-primary bg-primary/10 ring-2 ring-ring"
              : "border-border bg-card hover:border-primary/50"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-foreground">
              Modern 30/70
            </span>
            {template === "modern" && (
              <Badge variant="secondary" className="text-[10px]">
                Active
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            Sleek 2-column sidebar layout separating skills and experience.
          </p>
        </button>

        <button
          type="button"
          onClick={() => setTemplate("creative")}
          aria-pressed={template === "creative"}
          className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
            template === "creative"
              ? "border-primary bg-primary/10 ring-2 ring-ring"
              : "border-border bg-card hover:border-primary/50"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-foreground">
              Creative
            </span>
            {template === "creative" && (
              <Badge variant="secondary" className="text-[10px]">
                Active
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            Terminal dark theme stylized for DevOps, AI & Hackathons.
          </p>
        </button>

        <button
          type="button"
          onClick={() => setTemplate("minimalist")}
          aria-pressed={template === "minimalist"}
          className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
            template === "minimalist"
              ? "border-primary bg-primary/10 ring-2 ring-ring"
              : "border-border bg-card hover:border-primary/50"
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-sm font-bold text-foreground">
              Minimalist
            </span>
            {template === "minimalist" && (
              <Badge variant="secondary" className="text-[10px]">
                Active
              </Badge>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">
            Serif classic typography for Masters, R&D & Data Science.
          </p>
        </button>
      </div>

      {/* Editor + Live Document View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Control Panel (5 cols) */}
        <div className="lg:col-span-5 space-y-4 print:hidden">
          {/* AI Tailoring Card */}
          <Card className="border-primary/30 bg-primary/5">
            <CardHeader className="py-3">
              <CardTitle className="text-xs font-bold text-primary flex items-center justify-between">
                <span>AI Job Description Tailoring</span>
                <span className="text-[10px] font-mono text-primary">
                  STAR Generator
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Textarea
                placeholder="Paste job description (JD) to align skills and re-word bullets..."
                value={targetJd}
                onChange={(e) => setTargetJd(e.target.value)}
                rows={3}
                className="text-xs bg-background"
              />
              <Button
                onClick={handleAiOptimize}
                disabled={isOptimizing}
                size="sm"
                className="w-full text-xs font-medium cursor-pointer"
              >
                {isOptimizing
                  ? "Tailoring against the job description…"
                  : "Run AI ATS Tailor"}
              </Button>
              {aiError && <p className="text-xs text-destructive">{aiError}</p>}
              {factCheckFindings && factCheckFindings.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-warning">
                  {factCheckFindings.map((claim, i) => (
                    <li key={i}>{claim}</li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Section Navigation Tabs */}
          <div className="flex border-b border-border text-xs gap-2">
            {(
              [
                "contact",
                "skills",
                "experience",
                "projects",
                "education",
              ] as const
            ).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                aria-pressed={activeTab === tab}
                className={`py-2 px-3 capitalize border-b-2 font-medium transition-colors cursor-pointer ${
                  activeTab === tab
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Tab Content 1: Contact Details */}
          {activeTab === "contact" && (
            <Card>
              <CardContent className="pt-4 space-y-3 text-xs">
                <div>
                  <label className="text-muted-foreground font-medium">
                    Full Name
                  </label>
                  <Input
                    value={data.fullName}
                    placeholder="Ada Lovelace"
                    onChange={(e) =>
                      setData({ ...data, fullName: e.target.value })
                    }
                  />
                </div>
                <div>
                  <label className="text-muted-foreground font-medium">
                    Target Role Title
                  </label>
                  <Input
                    value={data.roleTitle}
                    placeholder="Backend Engineer"
                    onChange={(e) =>
                      setData({ ...data, roleTitle: e.target.value })
                    }
                  />
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <div>
                    <label className="text-muted-foreground font-medium">
                      Email
                    </label>
                    <Input
                      value={data.email}
                      placeholder="you@example.com"
                      onChange={(e) =>
                        setData({ ...data, email: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-muted-foreground font-medium">
                      Phone
                    </label>
                    <Input
                      value={data.phone}
                      placeholder="+91 98765 43210"
                      onChange={(e) =>
                        setData({ ...data, phone: e.target.value })
                      }
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <div>
                    <label className="text-muted-foreground font-medium">
                      LinkedIn
                    </label>
                    <Input
                      value={data.linkedin}
                      placeholder="linkedin.com/in/yourname"
                      onChange={(e) =>
                        setData({ ...data, linkedin: e.target.value })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-muted-foreground font-medium">
                      GitHub
                    </label>
                    <Input
                      value={data.github}
                      placeholder="github.com/yourname"
                      onChange={(e) =>
                        setData({ ...data, github: e.target.value })
                      }
                    />
                  </div>
                </div>
                <div>
                  <label className="text-muted-foreground font-medium">
                    Professional Summary
                  </label>
                  <Textarea
                    value={data.summary}
                    onChange={(e) =>
                      setData({ ...data, summary: e.target.value })
                    }
                    rows={4}
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Tab Content 2: Technical Skills */}
          {activeTab === "skills" && (
            <Card>
              <CardContent className="pt-4 space-y-3 text-xs">
                <div>
                  <label className="text-muted-foreground font-medium">
                    Programming Languages
                  </label>
                  <Input
                    value={data.skills.languages}
                    onChange={(e) =>
                      setData({
                        ...data,
                        skills: { ...data.skills, languages: e.target.value },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-muted-foreground font-medium">
                    Frameworks & Libraries
                  </label>
                  <Input
                    value={data.skills.frameworks}
                    onChange={(e) =>
                      setData({
                        ...data,
                        skills: { ...data.skills, frameworks: e.target.value },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-muted-foreground font-medium">
                    Databases & Vector DBs
                  </label>
                  <Input
                    value={data.skills.databases}
                    onChange={(e) =>
                      setData({
                        ...data,
                        skills: { ...data.skills, databases: e.target.value },
                      })
                    }
                  />
                </div>
                <div>
                  <label className="text-muted-foreground font-medium">
                    Developer Tools & Cloud
                  </label>
                  <Input
                    value={data.skills.tools}
                    onChange={(e) =>
                      setData({
                        ...data,
                        skills: { ...data.skills, tools: e.target.value },
                      })
                    }
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Tab Content 3: Experience */}
          {activeTab === "experience" && (
            <div className="space-y-4">
              {data.experience.map((exp, idx) => (
                <Card key={exp.id}>
                  <CardHeader className="py-2.5 flex flex-row items-center justify-between">
                    <CardTitle className="text-xs font-bold">
                      Experience #{idx + 1}
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeExperience(exp.id)}
                      className="h-6 text-xs text-destructive"
                    >
                      Remove
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs">
                    <Input
                      placeholder="Company"
                      value={exp.company}
                      onChange={(e) => {
                        const val = e.target.value;
                        setData((prev) => ({
                          ...prev,
                          experience: prev.experience.map((item) =>
                            item.id === exp.id
                              ? { ...item, company: val }
                              : item,
                          ),
                        }));
                      }}
                    />
                    <Input
                      placeholder="Role"
                      value={exp.role}
                      onChange={(e) => {
                        const val = e.target.value;
                        setData((prev) => ({
                          ...prev,
                          experience: prev.experience.map((item) =>
                            item.id === exp.id ? { ...item, role: val } : item,
                          ),
                        }));
                      }}
                    />
                    <Input
                      placeholder="Dates (e.g. 2024 - Present)"
                      value={exp.dates}
                      onChange={(e) => {
                        const val = e.target.value;
                        setData((prev) => ({
                          ...prev,
                          experience: prev.experience.map((item) =>
                            item.id === exp.id ? { ...item, dates: val } : item,
                          ),
                        }));
                      }}
                    />
                  </CardContent>
                </Card>
              ))}
              <Button
                onClick={addExperience}
                variant="outline"
                size="sm"
                className="w-full text-xs cursor-pointer"
              >
                + Add Experience Position
              </Button>
            </div>
          )}

          {/* Tab Content 4: Projects */}
          {activeTab === "projects" && (
            <div className="space-y-4">
              {data.projects.map((proj, idx) => (
                <Card key={proj.id}>
                  <CardHeader className="py-2.5 flex flex-row items-center justify-between">
                    <CardTitle className="text-xs font-bold">
                      Project #{idx + 1}
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeProject(proj.id)}
                      className="h-6 text-xs text-destructive"
                    >
                      Remove
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-2 text-xs">
                    <Input
                      placeholder="Project Title"
                      value={proj.title}
                      onChange={(e) => {
                        const val = e.target.value;
                        setData((prev) => ({
                          ...prev,
                          projects: prev.projects.map((item) =>
                            item.id === proj.id
                              ? { ...item, title: val }
                              : item,
                          ),
                        }));
                      }}
                    />
                    <Input
                      placeholder="Technologies (e.g. React, Next.js, FastAPI)"
                      value={proj.technologies}
                      onChange={(e) => {
                        const val = e.target.value;
                        setData((prev) => ({
                          ...prev,
                          projects: prev.projects.map((item) =>
                            item.id === proj.id
                              ? { ...item, technologies: val }
                              : item,
                          ),
                        }));
                      }}
                    />
                  </CardContent>
                </Card>
              ))}
              <Button
                onClick={addProject}
                variant="outline"
                size="sm"
                className="w-full text-xs cursor-pointer"
              >
                + Add Key Project
              </Button>
            </div>
          )}

          {/* Tab Content 5: Education */}
          {activeTab === "education" && (
            <div className="space-y-4">
              {data.education.map((edu) => (
                <Card key={edu.id}>
                  <CardContent className="pt-4 space-y-2 text-xs">
                    <Input
                      placeholder="Institution"
                      value={edu.institution}
                      onChange={(e) => {
                        const val = e.target.value;
                        setData((prev) => ({
                          ...prev,
                          education: prev.education.map((item) =>
                            item.id === edu.id
                              ? { ...item, institution: val }
                              : item,
                          ),
                        }));
                      }}
                    />
                    <Input
                      placeholder="Degree"
                      value={edu.degree}
                      onChange={(e) => {
                        const val = e.target.value;
                        setData((prev) => ({
                          ...prev,
                          education: prev.education.map((item) =>
                            item.id === edu.id
                              ? { ...item, degree: val }
                              : item,
                          ),
                        }));
                      }}
                    />
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <Input
                        placeholder="Dates"
                        value={edu.dates}
                        onChange={(e) => {
                          const val = e.target.value;
                          setData((prev) => ({
                            ...prev,
                            education: prev.education.map((item) =>
                              item.id === edu.id
                                ? { ...item, dates: val }
                                : item,
                            ),
                          }));
                        }}
                      />
                      <Input
                        placeholder="GPA / Marks"
                        value={edu.gpa}
                        onChange={(e) => {
                          const val = e.target.value;
                          setData((prev) => ({
                            ...prev,
                            education: prev.education.map((item) =>
                              item.id === edu.id ? { ...item, gpa: val } : item,
                            ),
                          }));
                        }}
                      />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Right Live Document Sheet (7 cols) */}
        <div className="lg:col-span-7">
          <div className="sticky top-6">
            <div className="text-xs text-muted-foreground mb-2 flex justify-between items-center print:hidden">
              <span>Live ATS Document ({template.toUpperCase()} Template)</span>
              <span className="font-mono text-success font-medium">
                Single-Page Strict Format
              </span>
            </div>

            {/* Printable Document Frame */}
            <div
              id="resume-document"
              className="bg-card text-foreground shadow-overlay rounded-sm p-8 min-h-[850px] border border-border print:shadow-none print:border-none print:p-0 print:m-0 font-sans select-text"
            >
              {template === "apex" && <ApexTemplate data={data} />}
              {template === "modern" && <ModernTemplate data={data} />}
              {template === "creative" && <CreativeTemplate data={data} />}
              {template === "minimalist" && <MinimalistTemplate data={data} />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

{
  /* --- Template 1: Apex Resume (Universal 1-Column LaTeX Standard) --- */
}
function ApexTemplate({ data }: { data: ResumeData }) {
  return (
    <div className="space-y-3.5 text-[11.5px] leading-relaxed text-foreground font-sans">
      {/* Header */}
      <div className="text-center border-b border-border pb-2.5">
        <h1 className="text-2xl font-bold uppercase tracking-wider text-foreground">
          {data.fullName}
        </h1>
        <div className="flex flex-wrap justify-center gap-1.5 text-[10.5px] text-foreground mt-1 font-medium">
          <span>{data.phone}</span>
          <span>|</span>
          <span>{data.email}</span>
          <span>|</span>
          <span>{data.linkedin}</span>
          <span>|</span>
          <span>{data.github}</span>
        </div>
      </div>

      {/* Summary */}
      {data.summary && (
        <section>
          <h2 className="text-[11.5px] font-bold uppercase tracking-wider border-b border-border pb-0.5 mb-1 text-foreground">
            Professional Summary
          </h2>
          <p className="text-foreground text-[11px] leading-snug">
            {data.summary}
          </p>
        </section>
      )}

      {/* Technical Skills */}
      <section>
        <h2 className="text-[11.5px] font-bold uppercase tracking-wider border-b border-border pb-0.5 mb-1 text-foreground">
          Technical Skills
        </h2>
        <div className="space-y-0.5 text-[11px] text-foreground">
          {data.skills.languages && (
            <div>
              <span className="font-bold text-foreground">Languages:</span>{" "}
              {data.skills.languages}
            </div>
          )}
          {data.skills.frameworks && (
            <div>
              <span className="font-bold text-foreground">
                Frameworks & Libraries:
              </span>{" "}
              {data.skills.frameworks}
            </div>
          )}
          {data.skills.databases && (
            <div>
              <span className="font-bold text-foreground">
                Databases & Infrastructure:
              </span>{" "}
              {data.skills.databases}
            </div>
          )}
          {data.skills.tools && (
            <div>
              <span className="font-bold text-foreground">
                Tools & Cloud Services:
              </span>{" "}
              {data.skills.tools}
            </div>
          )}
        </div>
      </section>

      {/* Experience */}
      {data.experience.length > 0 && (
        <section>
          <h2 className="text-[11.5px] font-bold uppercase tracking-wider border-b border-border pb-0.5 mb-1.5 text-foreground">
            Experience
          </h2>
          <div className="space-y-2.5">
            {data.experience.map((exp) => (
              <div key={exp.id}>
                <div className="flex justify-between items-baseline font-bold text-foreground">
                  <span>
                    {exp.company} -{" "}
                    <span className="italic font-normal text-foreground">
                      {exp.role}
                    </span>
                  </span>
                  <span className="text-[10.5px] text-foreground font-normal">
                    {exp.dates}
                  </span>
                </div>
                <ul className="list-disc pl-4 mt-0.5 space-y-0.5 text-[11px] text-foreground leading-tight">
                  {exp.bullets.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Key Projects */}
      {data.projects.length > 0 && (
        <section>
          <h2 className="text-[11.5px] font-bold uppercase tracking-wider border-b border-border pb-0.5 mb-1.5 text-foreground">
            Key Projects
          </h2>
          <div className="space-y-2.5">
            {data.projects.map((proj) => (
              <div key={proj.id}>
                <div className="flex justify-between items-baseline font-bold text-foreground">
                  <span>
                    {proj.title}{" "}
                    <span className="font-normal text-[10.5px] text-foreground">
                      | {proj.technologies}
                    </span>
                  </span>
                  <span className="text-[10.5px] text-foreground font-normal">
                    {proj.dates}
                  </span>
                </div>
                <ul className="list-disc pl-4 mt-0.5 space-y-0.5 text-[11px] text-foreground leading-tight">
                  {proj.bullets.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Education */}
      {data.education.length > 0 && (
        <section>
          <h2 className="text-[11.5px] font-bold uppercase tracking-wider border-b border-border pb-0.5 mb-1 text-foreground">
            Education
          </h2>
          <div className="space-y-1">
            {data.education.map((edu) => (
              <div
                key={edu.id}
                className="flex justify-between items-baseline text-[11px]"
              >
                <div>
                  <span className="font-bold text-foreground">
                    {edu.institution}
                  </span>{" "}
                  - <span className="text-foreground">{edu.degree}</span>
                </div>
                <div className="text-[10.5px] text-foreground">
                  {edu.gpa} ({edu.dates})
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

{
  /* --- Template 2: Modern 30/70 Split --- */
}
function ModernTemplate({ data }: { data: ResumeData }) {
  return (
    <div className="grid grid-cols-12 gap-5 text-[11.5px] text-foreground font-sans">
      <div className="col-span-4 border-r border-border pr-3.5 space-y-3.5">
        <div>
          <h1 className="text-xl font-semibold text-primary leading-tight">
            {data.fullName}
          </h1>
          <p className="text-[11px] text-primary font-bold mt-0.5">
            {data.roleTitle}
          </p>
        </div>

        <div className="space-y-1 text-[10.5px] text-foreground">
          <div>{data.email}</div>
          <div>{data.phone}</div>
          <div>{data.location}</div>
          <div className="text-primary font-medium">{data.github}</div>
        </div>

        <section>
          <h3 className="font-bold text-[11px] uppercase tracking-wider text-primary border-b border-primary pb-0.5 mb-1.5">
            Technical Skills
          </h3>
          <div className="space-y-1.5 text-[10.5px]">
            <div>
              <div className="font-bold text-foreground">Languages</div>
              <div className="text-foreground">{data.skills.languages}</div>
            </div>
            <div>
              <div className="font-bold text-foreground">Frameworks</div>
              <div className="text-foreground">{data.skills.frameworks}</div>
            </div>
            <div>
              <div className="font-bold text-foreground">Databases</div>
              <div className="text-foreground">{data.skills.databases}</div>
            </div>
          </div>
        </section>
      </div>

      <div className="col-span-8 space-y-3.5">
        {data.summary && (
          <section>
            <h2 className="font-bold text-[11.5px] uppercase text-primary border-b border-border pb-0.5 mb-1">
              Profile
            </h2>
            <p className="text-foreground text-[11px] leading-snug">
              {data.summary}
            </p>
          </section>
        )}

        <section>
          <h2 className="font-bold text-[11.5px] uppercase text-primary border-b border-border pb-0.5 mb-1.5">
            Experience
          </h2>
          {data.experience.map((exp) => (
            <div key={exp.id} className="mb-2.5">
              <div className="font-bold text-foreground">
                {exp.role}{" "}
                <span className="font-normal text-foreground">
                  @ {exp.company}
                </span>
              </div>
              <ul className="list-disc pl-4 mt-0.5 space-y-0.5 text-[11px] text-foreground">
                {exp.bullets.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>

        <section>
          <h2 className="font-bold text-[11.5px] uppercase text-primary border-b border-border pb-0.5 mb-1.5">
            Projects
          </h2>
          {data.projects.map((proj) => (
            <div key={proj.id} className="mb-2.5">
              <div className="font-bold text-foreground">{proj.title}</div>
              <ul className="list-disc pl-4 mt-0.5 space-y-0.5 text-[11px] text-foreground">
                {proj.bullets.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

{
  /* --- Template 3: Creative Hacker Terminal --- */
}
function CreativeTemplate({ data }: { data: ResumeData }) {
  return (
    <div className="space-y-3.5 text-[11px] text-success bg-foreground p-6 rounded-md font-mono border border-success/20">
      <div className="border-b border-success/20 pb-2">
        <div className="text-base font-bold text-success">$ whoami</div>
        <div className="text-success font-bold">
          {data.fullName} {"//"} {data.roleTitle}
        </div>
        <div className="text-muted-foreground text-[10px]">
          {data.email} | {data.github} | {data.linkedin}
        </div>
      </div>

      <section>
        <div className="text-success font-bold">$ cat summary.txt</div>
        <p className="text-muted-foreground text-[10.5px] leading-relaxed mt-0.5">
          {data.summary}
        </p>
      </section>

      <section>
        <div className="text-success font-bold">$ ./list_skills.sh</div>
        <div className="text-muted-foreground text-[10.5px] mt-0.5 space-y-0.5">
          <div>
            <span className="text-success">LANGUAGES:</span>{" "}
            {data.skills.languages}
          </div>
          <div>
            <span className="text-success">FRAMEWORKS:</span>{" "}
            {data.skills.frameworks}
          </div>
          <div>
            <span className="text-success">DATABASES:</span>{" "}
            {data.skills.databases}
          </div>
        </div>
      </section>

      <section>
        <div className="text-success font-bold">$ git log --experience</div>
        {data.experience.map((exp) => (
          <div
            key={exp.id}
            className="mt-1.5 text-muted-foreground text-[10.5px]"
          >
            <div className="font-bold text-success">
              &gt; {exp.role} @ {exp.company} ({exp.dates})
            </div>
            <ul className="list-disc pl-4 space-y-0.5 text-muted-foreground mt-0.5">
              {exp.bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}

{
  /* --- Template 4: Minimalist Academic --- */
}
function MinimalistTemplate({ data }: { data: ResumeData }) {
  return (
    <div className="space-y-3.5 text-[11.5px] text-foreground font-serif leading-relaxed">
      <div className="text-center pb-2">
        <h1 className="text-2xl font-normal text-foreground">
          {data.fullName}
        </h1>
        <div className="text-[10.5px] text-foreground italic mt-0.5">
          {data.roleTitle} - {data.email} • {data.phone}
        </div>
      </div>

      {data.summary && (
        <section>
          <h2 className="text-[11.5px] font-bold italic border-b border-border pb-0.5 mb-1 text-foreground">
            Summary
          </h2>
          <p className="text-foreground text-[11px] leading-snug">
            {data.summary}
          </p>
        </section>
      )}

      <section>
        <h2 className="text-[11.5px] font-bold italic border-b border-border pb-0.5 mb-1 text-foreground">
          Experience
        </h2>
        {data.experience.map((exp) => (
          <div key={exp.id} className="mb-2">
            <div className="flex justify-between italic text-foreground">
              <span className="font-bold">
                {exp.company} - {exp.role}
              </span>
              <span className="text-muted-foreground text-[10.5px]">
                {exp.dates}
              </span>
            </div>
            <ul className="list-disc pl-4 mt-0.5 text-foreground space-y-0.5 text-[11px]">
              {exp.bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  );
}
