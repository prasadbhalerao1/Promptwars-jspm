export type Role = "candidate" | "recruiter" | "organizer" | "judge" | "admin";

export interface RoleMetadata {
  value: Role;
  label: string;
  shortLabel: string;
  description: string;
  greeting: string;
  defaultPath: string;
  badgeVariant: "default" | "secondary" | "outline";
}

export const ROLES: readonly Role[] = [
  "candidate",
  "recruiter",
  "organizer",
  "judge",
  "admin",
] as const;

export const ROLE_METADATA: Record<Role, RoleMetadata> = {
  candidate: {
    value: "candidate",
    label: "Candidate",
    shortLabel: "Candidate",
    description: "Build evidence recruiters can actually verify.",
    greeting: "Build evidence recruiters can actually verify.",
    defaultPath: "/home",
    badgeVariant: "default",
  },
  recruiter: {
    value: "recruiter",
    label: "Recruiter",
    shortLabel: "Recruiter",
    description: "Find candidates by what they've built, not what they claim.",
    greeting: "Find candidates by what they've built, not what they claim.",
    defaultPath: "/home",
    badgeVariant: "secondary",
  },
  organizer: {
    value: "organizer",
    label: "Hackathon Organizer",
    shortLabel: "Organizer",
    description: "Run events and turn results into hiring signal.",
    greeting: "Run events and turn results into hiring signal.",
    defaultPath: "/home",
    badgeVariant: "outline",
  },
  judge: {
    value: "judge",
    label: "Judge",
    shortLabel: "Judge",
    description: "Score submissions against a consistent rubric.",
    greeting: "Score submissions against a consistent rubric.",
    defaultPath: "/home",
    badgeVariant: "outline",
  },
  admin: {
    value: "admin",
    label: "Admin",
    shortLabel: "Admin",
    description: "Keep the platform trustworthy and its records clean.",
    greeting: "Keep the platform trustworthy and its records clean.",
    defaultPath: "/home",
    badgeVariant: "secondary",
  },
};

/** Roles a visitor may assign themselves on the sign-up form.
 *
 * Deliberately a subset of `ROLES` rather than all of it. This list used to be
 * `ROLES.map(...)`, so the form offered "Admin" in its dropdown — and the API accepted
 * it, because `SignupRequest.role` was the full role enum. Picking it from the menu
 * granted user management, role reassignment for every account, the audit log and the
 * trusted-issuer registry.
 *
 * `admin`, `organizer` and `judge` are assigned by an existing admin via
 * `PATCH /admin/users/{id}/role`. MUST stay in sync with `SignupRole` in
 * packages/shared_schemas/users.py, which is the half that actually enforces;
 * services/api/tests/test_signup_roles.py asserts the two agree.
 */
export const SIGNUP_ROLES: readonly Role[] = ["candidate", "recruiter"] as const;

export const SIGNUP_ROLE_OPTIONS = SIGNUP_ROLES.map((r) => ({
  value: r,
  label: ROLE_METADATA[r].label,
}));

export const USERNAME_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])?$/;

export const RESERVED_USERNAMES = new Set([
  "api",
  "dashboard",
  "onboarding",
  "sign-in",
  "sign-up",
  "hackathons",
  "profile",
  "career",
  "resume-builder",
  "assessments",
  "interview",
  "my-flags",
  "applications",
  "jobs",
  "copilot",
  "pipeline",
  "analytics",
  "top-performers",
  "reports",
  "evaluations",
  "submissions",
  "fraud-review",
  "users",
  "audit-log",
  "candidates",
  "public",
  "me",
  "health",
  "home",
  "admin",
  "recruiter",
  "organizer",
  "judge",
  "settings",
]);

