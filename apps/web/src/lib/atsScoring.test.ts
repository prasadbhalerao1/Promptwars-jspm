import { describe, expect, it } from "vitest";

import { calculateATSScore, type ResumeData } from "./atsScoring";

/** The résumé builder's live ATS score: what it rewards and what it flags.
 *
 * Asserted on behaviour (ordering, ranges, the issues reported) rather than on every exact
 * number, so retuning a weight does not break the suite but a scorer that stops noticing a
 * missing email, or ranks an empty résumé above a strong one, does. */

const EMPTY: ResumeData = {
  fullName: "",
  roleTitle: "",
  phone: "",
  email: "",
  location: "",
  linkedin: "",
  github: "",
  portfolio: "",
  summary: "",
  skills: { languages: "", frameworks: "", tools: "", databases: "", cloud: "" },
  experience: [],
  projects: [],
  education: [],
};

const STRONG: ResumeData = {
  fullName: "Asha Kulkarni",
  roleTitle: "Backend Engineer",
  phone: "+91 98765 43210",
  email: "asha.kulkarni@example.com",
  location: "Pune, India",
  linkedin: "",
  github: "github.com/asha-k",
  portfolio: "asha.dev",
  summary:
    "Backend engineer with 4 years building Python and FastAPI services on PostgreSQL and Redis. Led a migration that reduced p95 latency by 40% and improved deploy frequency.",
  skills: {
    languages: "Python, TypeScript, SQL",
    frameworks: "FastAPI, React, Next.js",
    tools: "Docker, Kubernetes, Git",
    databases: "PostgreSQL, Redis, MongoDB",
    cloud: "AWS, GCP",
  },
  experience: [
    {
      id: "e1",
      company: "Finly",
      role: "Backend Engineer",
      location: "Pune",
      dates: "2022 - Present",
      bullets: [
        "Architected a FastAPI payments service handling 2 million requests per day with 99.95% uptime.",
        "Optimized PostgreSQL queries and added Redis caching, reducing p95 latency by 40%.",
        "Led a team of 3 engineers to deliver a CI/CD pipeline that increased deploy frequency 5x.",
      ],
    },
    {
      id: "e2",
      company: "CodeCraft",
      role: "Software Engineer",
      location: "Mumbai",
      dates: "2020 - 2022",
      bullets: [
        "Developed REST and GraphQL APIs consumed by 12 internal teams.",
        "Implemented Docker and Kubernetes deployments, improving release reliability by 30%.",
      ],
    },
  ],
  projects: [
    {
      id: "p1",
      title: "Realtime Leaderboard",
      technologies: "Next.js, Redis, WebSockets",
      dates: "2023",
      bullets: ["Scaled a realtime leaderboard to 50 thousand concurrent users."],
    },
  ],
  education: [
    {
      id: "ed1",
      institution: "Pune University",
      degree: "B.E. Computer Engineering",
      dates: "2016 - 2020",
      gpa: "8.6",
    },
  ],
};

const CATEGORIES = ["parsing", "contact", "keywords", "formatting", "content"] as const;

describe("calculateATSScore", () => {
  it("keeps the total and every category within 0-100", () => {
    for (const resume of [EMPTY, STRONG]) {
      const result = calculateATSScore(resume);
      expect(result.score).toBeGreaterThanOrEqual(0);
      expect(result.score).toBeLessThanOrEqual(100);
      for (const category of CATEGORIES) {
        expect(result.breakdown[category].score).toBeGreaterThanOrEqual(0);
        expect(result.breakdown[category].score).toBeLessThanOrEqual(100);
      }
    }
  });

  it("returns an integer total", () => {
    expect(Number.isInteger(calculateATSScore(STRONG).score)).toBe(true);
  });

  it("ranks a complete, quantified résumé well above an empty one", () => {
    const strong = calculateATSScore(STRONG).score;
    const empty = calculateATSScore(EMPTY).score;
    expect(strong).toBeGreaterThan(empty + 30);
  });

  it("explains what is missing from an empty résumé", () => {
    const issues = calculateATSScore(EMPTY).breakdown.parsing.issues.join(" | ");
    expect(issues).toMatch(/full name/i);
    expect(issues).toMatch(/email/i);
    expect(issues).toMatch(/experience/i);
    expect(issues).toMatch(/education/i);
  });

  it("reports no parsing problems for a complete résumé", () => {
    const { parsing } = calculateATSScore(STRONG).breakdown;
    expect(parsing.issues).toEqual([]);
    expect(parsing.score).toBe(100);
  });

  it("flags a malformed email address and lowers the parsing score", () => {
    const broken = calculateATSScore({ ...STRONG, email: "asha.example.com" });
    expect(broken.breakdown.parsing.issues.join(" ")).toMatch(/email format invalid/i);
    expect(broken.breakdown.parsing.score).toBeLessThan(100);
    expect(broken.score).toBeLessThanOrEqual(calculateATSScore(STRONG).score);
  });

  it("rewards relevant keywords: stripping skills and impact words lowers the keyword score", () => {
    const bare: ResumeData = {
      ...STRONG,
      summary: "Engineer.",
      skills: { languages: "", frameworks: "", tools: "", databases: "", cloud: "" },
      experience: STRONG.experience.map((e) => ({ ...e, bullets: ["Worked on things."] })),
      projects: [],
    };
    expect(calculateATSScore(bare).breakdown.keywords.score).toBeLessThan(
      calculateATSScore(STRONG).breakdown.keywords.score,
    );
  });

  it("does not mutate its input", () => {
    const snapshot = JSON.stringify(STRONG);
    calculateATSScore(STRONG);
    expect(JSON.stringify(STRONG)).toBe(snapshot);
  });
});
