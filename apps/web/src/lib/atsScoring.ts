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
  experience: Array<{
    id: string;
    company: string;
    role: string;
    location: string;
    dates: string;
    bullets: string[];
  }>;
  projects: Array<{
    id: string;
    title: string;
    technologies: string;
    dates: string;
    bullets: string[];
  }>;
  education: Array<{
    id: string;
    institution: string;
    degree: string;
    dates: string;
    gpa: string;
  }>;
}

export interface ATSScoreDetail {
  score: number;
  breakdown: {
    parsing: { score: number; issues: string[] };
    contact: { score: number; issues: string[] };
    keywords: { score: number; issues: string[] };
    formatting: { score: number; issues: string[] };
    content: { score: number; issues: string[] };
  };
}

const CRITICAL_ATS_KEYWORDS = [
  // Technical Skills
  "javascript",
  "typescript",
  "python",
  "java",
  "c++",
  "sql",
  "html",
  "css",
  "react",
  "next.js",
  "vue",
  "angular",
  "node.js",
  "express",
  "fastapi",
  "django",
  "postgresql",
  "mongodb",
  "redis",
  "mysql",
  "dynamodb",
  "firestore",
  "aws",
  "azure",
  "gcp",
  "google cloud",
  "docker",
  "kubernetes",
  "git",

  // Business & Soft Skills
  "leadership",
  "communication",
  "problem solving",
  "project management",
  "agile",
  "scrum",
  "sprint",
  "kanban",
  "ci/cd",
  "devops",
  "api",
  "rest",
  "graphql",
  "microservices",
  "cloud",

  // Metrics & Impact Words
  "improved",
  "increased",
  "reduced",
  "optimized",
  "engineered",
  "architected",
  "designed",
  "implemented",
  "developed",
  "launched",
  "scaled",
  "achieved",
  "delivered",
  "collaborated",
  "managed",
  "led",

  // Percent & Numbers (important for ATS)
  "%",
  "x",
  "roi",
  "revenue",
  "growth",
  "performance",
  "million",
  "thousand",
];

export function calculateATSScore(data: ResumeData): ATSScoreDetail {
  const breakdown = {
    parsing: calculateParsingScore(data),
    contact: calculateContactScore(data),
    keywords: calculateKeywordScore(data),
    formatting: calculateFormattingScore(data),
    content: calculateContentScore(data),
  };

  const totalScore = Math.round(
    breakdown.parsing.score * 0.15 +
      breakdown.contact.score * 0.15 +
      breakdown.keywords.score * 0.25 +
      breakdown.formatting.score * 0.15 +
      breakdown.content.score * 0.3,
  );

  return {
    score: Math.max(0, Math.min(100, totalScore)),
    breakdown,
  };
}

function calculateParsingScore(data: ResumeData): {
  score: number;
  issues: string[];
} {
  const issues: string[] = [];
  let score = 100;

  if (!data.fullName?.trim()) {
    issues.push("Missing full name. ATS cannot identify the applicant");
    score -= 20;
  }

  if (!data.email?.trim()) {
    issues.push("No email address. ATS cannot contact you");
    score -= 20;
  }

  if (!data.phone?.trim()) {
    issues.push("No phone number. Backup contact is missing");
    score -= 10;
  }

  if (!hasValidEmailFormat(data.email)) {
    issues.push("Email format invalid");
    score -= 15;
  }

  if (!hasValidPhoneFormat(data.phone)) {
    issues.push("Phone format may not parse correctly");
    score -= 5;
  }

  if (!data.experience || data.experience.length === 0) {
    issues.push("No work experience detected");
    score -= 15;
  }

  if (!data.education || data.education.length === 0) {
    issues.push("No education listed");
    score -= 10;
  }

  return { score: Math.max(0, score), issues };
}

function calculateContactScore(data: ResumeData): {
  score: number;
  issues: string[];
} {
  const issues: string[] = [];
  let score = 100;

  const contactFields = [
    { field: "full name", value: data.fullName, weight: 20 },
    { field: "email", value: data.email, weight: 20 },
    { field: "phone", value: data.phone, weight: 15 },
    { field: "location", value: data.location, weight: 10 },
    { field: "LinkedIn URL", value: data.linkedin, weight: 15 },
    { field: "GitHub URL", value: data.github, weight: 10 },
  ];

  contactFields.forEach(({ field, value, weight }) => {
    if (!value?.trim()) {
      issues.push(`Missing ${field}`);
      score -= weight;
    }
  });

  if (data.linkedin && !isValidUrl(data.linkedin)) {
    issues.push("LinkedIn URL may not be properly formatted");
    score -= 5;
  }

  if (data.github && !isValidUrl(data.github)) {
    issues.push("GitHub URL may not be properly formatted");
    score -= 5;
  }

  return { score: Math.max(0, score), issues };
}

function calculateKeywordScore(data: ResumeData): {
  score: number;
  issues: string[];
} {
  const issues: string[] = [];
  let score = 0;
  const keywordMatches = new Set<string>();

  const fullText = getResumeText(data).toLowerCase();
  const wordSet = new Set(fullText.split(/\s+/));

  CRITICAL_ATS_KEYWORDS.forEach((keyword) => {
    if (wordSet.has(keyword)) {
      keywordMatches.add(keyword);
      score += 2;
    }
  });

  // Check for quantified achievements (numbers/percentages)
  const hasNumbers = /(\d+%|\d+x|\$\d+[mk]?|\d+\+|\b\d{4,}\b)/i.test(fullText);
  if (hasNumbers) {
    score += 15;
    keywordMatches.add("quantified achievements");
  } else {
    issues.push(
      "No quantified results found (add metrics like %, $, x multiplier)",
    );
    score -= 10;
  }

  // Check for impact action verbs
  const impactVerbs = [
    "led",
    "architected",
    "engineered",
    "optimized",
    "scaled",
    "delivered",
  ];
  const hasImpactVerbs = impactVerbs.some((verb) =>
    new RegExp(`\\b${verb}\\b`, "i").test(fullText),
  );
  if (hasImpactVerbs) {
    score += 10;
  } else {
    issues.push(
      "Resume lacks strong action verbs (add: led, engineered, optimized, scaled)",
    );
    score -= 5;
  }

  if (keywordMatches.size < 10) {
    issues.push(
      `Low keyword density: found only ${keywordMatches.size} ATS keywords (ideal: 15+)`,
    );
    score = Math.max(score - 15, 0);
  }

  return { score: Math.min(score, 100), issues };
}

function calculateFormattingScore(data: ResumeData): {
  score: number;
  issues: string[];
} {
  const issues: string[] = [];
  let score = 100;

  // Check for excessive formatting that breaks ATS parsing
  const fullText = getResumeText(data);

  // Detect potential formatting issues
  if (
    fullText.includes("•") ||
    fullText.includes("◦") ||
    fullText.includes("‣")
  ) {
    score -= 5; // Non-standard bullets
  }

  if (data.experience.some((exp) => !exp.bullets || exp.bullets.length === 0)) {
    issues.push("Some experience entries lack bullet points");
    score -= 10;
  }

  if (
    data.projects.some((proj) => !proj.bullets || proj.bullets.length === 0)
  ) {
    issues.push("Some projects lack descriptions");
    score -= 5;
  }

  // Check section organization
  const hasSummary = data.summary?.trim().length > 20;
  const hasSkills =
    data.skills.languages?.trim() ||
    data.skills.frameworks?.trim() ||
    data.skills.databases?.trim();
  const hasExperience = data.experience.length > 0;
  const hasEducation = data.education.length > 0;

  const sections = [hasSummary, hasSkills, hasExperience, hasEducation].filter(
    Boolean,
  ).length;
  if (sections < 3) {
    issues.push(
      "Resume missing key sections (needs: Summary, Skills, Experience, Education)",
    );
    score -= 15;
  }

  // Check for proper date formatting
  const invalidDates = [
    ...data.experience.filter((exp) => !isValidDateRange(exp.dates)),
    ...data.projects.filter((proj) => !isValidDateRange(proj.dates)),
  ];
  if (invalidDates.length > 0) {
    issues.push(`${invalidDates.length} entries have poorly formatted dates`);
    score -= 10;
  }

  return { score: Math.max(0, score), issues };
}

function calculateContentScore(data: ResumeData): {
  score: number;
  issues: string[];
} {
  const issues: string[] = [];
  let score = 0;

  // Summary quality (50+ chars, ~1-3 lines)
  if (data.summary?.trim().length >= 80) {
    score += 20;
  } else if (data.summary?.trim().length >= 20) {
    score += 10;
    issues.push("Professional summary too brief (aim for 80+ characters)");
  } else {
    issues.push("Professional summary missing or too short");
    score -= 10;
  }

  // Skills completeness
  const skillCategories = [
    data.skills.languages,
    data.skills.frameworks,
    data.skills.databases,
    data.skills.tools,
    data.skills.cloud,
  ].filter((s) => s?.trim());
  score += Math.min(skillCategories.length * 15, 30);

  // Experience depth (each bullet point adds value)
  data.experience.forEach((exp) => {
    if (exp.bullets && exp.bullets.length >= 2) score += 8;
    else if (exp.bullets && exp.bullets.length === 1) score += 4;
    else score -= 5;
  });

  // Projects demonstrate capabilities
  if (data.projects.length >= 2) {
    score += 15;
  } else if (data.projects.length === 1) {
    score += 8;
  }

  // Education validation
  if (data.education.length > 0) {
    data.education.forEach((edu) => {
      if (edu.degree?.trim()) score += 10;
      if (edu.gpa?.trim()) score += 5;
    });
  }

  // Length check: ATS prefers 1-2 pages
  const totalLength = getResumeText(data).length;
  if (totalLength > 2000 && totalLength < 4500) {
    score += 10;
  } else if (totalLength > 4500) {
    issues.push(
      "Resume too long. ATS systems prefer 1-2 pages, and content may be truncated",
    );
    score -= 15;
  } else if (totalLength < 1500) {
    issues.push("Resume too short. Add more detail and impact statements");
    score -= 10;
  }

  return { score: Math.min(score, 100), issues };
}

// Helper functions
function hasValidEmailFormat(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function hasValidPhoneFormat(phone: string): boolean {
  return /\d{7,}/.test(phone.replace(/\D/g, ""));
}

function isValidUrl(url: string): boolean {
  try {
    new URL(url.startsWith("http") ? url : `https://${url}`);
    return true;
  } catch {
    return false;
  }
}

function isValidDateRange(dateStr: string): boolean {
  if (!dateStr) return false;
  const datePattern = /(\d{4}|\d{1,2}\/\d{1,2}|\w+\s+\d{4})/;
  return datePattern.test(dateStr);
}

function getResumeText(data: ResumeData): string {
  const parts = [
    data.fullName,
    data.roleTitle,
    data.summary,
    data.skills.languages,
    data.skills.frameworks,
    data.skills.databases,
    data.skills.tools,
    data.skills.cloud,
    ...data.experience.map(
      (e) => `${e.company} ${e.role} ${e.bullets.join(" ")}`,
    ),
    ...data.projects.map(
      (p) => `${p.title} ${p.technologies} ${p.bullets.join(" ")}`,
    ),
    ...data.education.map((e) => `${e.institution} ${e.degree}`),
  ];
  return parts.filter(Boolean).join(" ");
}
