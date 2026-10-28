import {
  Activity,
  Award,
  BarChart3,
  Braces,
  Brain,
  Building2,
  ClipboardCheck,
  FileText,
  Flag,
  Gavel,
  Globe,
  Home,
  LayoutDashboard,
  Lightbulb,
  ListChecks,
  Presentation,
  Search,
  ShieldAlert,
  Sparkles,
  Trophy,
  UserCog,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { ROLE_METADATA, type Role } from "@/lib/constants";

/** One thing a role can do.
 *
 * This is the single source of truth. The sidebar reads `label`, `icon` and `section`;
 * the `/home` hub reads `label` and `description`. Previously these were two
 * hand-maintained lists (`WORKSPACE_NAV` here and `ROLE_FEATURES` in lib/constants),
 * and they had already drifted: the recruiter sidebar carried a "Pipelines" entry the
 * hub grid did not, and an earlier "/recruiter/interviews" href pointed at a route that
 * never existed. One list cannot disagree with itself.
 */
export interface RoleCapability {
  href: string;
  /** Sidebar label and hub card title. */
  label: string;
  /** One line for the hub card. Omitted for entries that are navigation only. */
  description?: string;
  icon: LucideIcon;
  /** Sidebar grouping. Entries without one sit in the unlabelled first group. */
  section?: string;
  /** Match child routes too, so /jobs/new highlights "Browse jobs". Off by default so
   * sibling routes sharing a prefix do not both light up. */
  matchNested?: boolean;
  /** Hidden from the hub grid, shown in the sidebar. For `/home` itself, which would
   * otherwise be a card linking to the page it sits on. */
  navOnly?: boolean;
}

export type WorkspaceRole = Role;

export const ROLE_LABELS: Record<WorkspaceRole, string> = {
  candidate: ROLE_METADATA.candidate.shortLabel,
  recruiter: ROLE_METADATA.recruiter.shortLabel,
  admin: ROLE_METADATA.admin.shortLabel,
  organizer: ROLE_METADATA.organizer.shortLabel,
  judge: ROLE_METADATA.judge.shortLabel,
};

/** Section order per role. The sidebar renders groups in this order; anything not
 * listed here would be dropped, so a new section must be added in both places. */
const SECTION_ORDER: Record<WorkspaceRole, string[]> = {
  candidate: ["Profile", "Opportunities", "Practice", "Account"],
  recruiter: ["Hiring", "Evaluate"],
  admin: ["Trust & safety", "Platform"],
  organizer: ["Create"],
  judge: [],
};

/** Every capability, per role.
 *
 * Note on hrefs: Next route groups contribute nothing to the URL, so several natural
 * paths collide across roles and the workaround is recorded at the point of use.
 */
export const ROLE_CAPABILITIES: Record<WorkspaceRole, RoleCapability[]> = {
  candidate: [
    { href: "/home", label: "Home", icon: Home, navOnly: true },
    {
      href: "/dashboard",
      label: "Talent dashboard",
      description: "Your Talent Score, evidence receipts and GitHub analytics.",
      icon: LayoutDashboard,
    },
    {
      href: "/profile/edit",
      label: "Evidence & profile",
      description: "Connect GitHub, upload your résumé and certificates.",
      icon: Braces,
      section: "Profile",
    },
    {
      href: "/resume-builder",
      label: "Résumé & portfolio",
      description: "Generate an ATS-ready résumé and publish your portfolio.",
      icon: FileText,
      section: "Profile",
    },
    {
      href: "/career",
      label: "Career guidance",
      description: "Skill gaps, a learning roadmap and salary ranges.",
      icon: Lightbulb,
      section: "Profile",
    },
    {
      href: "/jobs",
      label: "Browse jobs",
      description: "Roles matched to your verified evidence.",
      icon: Search,
      section: "Opportunities",
    },
    {
      href: "/applications",
      label: "My applications",
      description: "Track where every application stands.",
      icon: ListChecks,
      section: "Opportunities",
    },
    {
      href: "/hackathons",
      label: "Hackathons",
      description: "Join events and get in front of recruiters.",
      icon: Trophy,
      section: "Opportunities",
      matchNested: true,
    },
    {
      href: "/interviews",
      label: "AI interview",
      description:
        "Practice with an adaptive interviewer and get a scored report.",
      icon: Brain,
      section: "Practice",
    },
    {
      href: "/assessments",
      label: "Assessments",
      description: "Timed coding problems that verify your skills.",
      icon: ClipboardCheck,
      section: "Practice",
      matchNested: true,
    },
    {
      href: "/pitch-deck",
      label: "Pitch deck analyzer",
      description: "Score a deck on clarity, innovation and feasibility.",
      icon: Presentation,
      section: "Practice",
    },
    {
      href: "/my-flags",
      label: "Disputes & flags",
      description: "Review and dispute anything raised on your profile.",
      icon: Flag,
      section: "Account",
    },
  ],

  recruiter: [
    { href: "/home", label: "Home", icon: Home, navOnly: true },
    {
      href: "/analytics",
      label: "Analytics",
      description: "Hiring funnel, time-to-hire and source breakdown.",
      icon: BarChart3,
    },
    {
      href: "/job-postings",
      label: "My jobs",
      description:
        "Manage postings, review ranked matches and open each pipeline.",
      icon: ListChecks,
      section: "Hiring",
    },
    {
      href: "/jobs/new",
      label: "Post a job",
      description: "Create a role and trigger candidate matching.",
      icon: Building2,
      section: "Hiring",
    },
    {
      href: "/copilot",
      label: "Copilot search",
      description: "Find candidates with plain-language search.",
      icon: Sparkles,
      section: "Evaluate",
    },
    {
      href: "/top-performers",
      label: "Top performers",
      description: "Standouts surfaced from hackathon results.",
      icon: Award,
      section: "Evaluate",
    },
    {
      // Not "/interviews": (candidate)/interviews already owns that path, and route
      // groups contribute nothing to the URL.
      href: "/interview-templates",
      label: "Interview templates",
      description: "Publish interview templates and read scored reports.",
      icon: Brain,
      section: "Evaluate",
    },
  ],

  admin: [
    { href: "/home", label: "Home", icon: Home, navOnly: true },
    {
      href: "/fraud-review",
      label: "Fraud review",
      description: "Adjudicate flags. Nothing penalizes until you uphold it.",
      icon: ShieldAlert,
      section: "Trust & safety",
      matchNested: true,
    },
    {
      href: "/trusted-issuers",
      label: "Trusted issuers",
      description: "Curate the certificate issuer registry.",
      icon: Globe,
      section: "Trust & safety",
    },
    {
      href: "/users",
      label: "Users & roles",
      description: "Manage accounts, roles and organizations.",
      icon: UserCog,
      section: "Platform",
    },
    {
      href: "/audit-log",
      label: "Audit log",
      description: "Every privileged action, with actor and target.",
      icon: Activity,
      section: "Platform",
    },
  ],

  organizer: [
    { href: "/home", label: "Home", icon: Home, navOnly: true },
    {
      // Not "/hackathons": that path belongs to (candidate)/hackathons, and pointing
      // here sent organizers into a candidate-gated route that bounced them to /home.
      href: "/events",
      label: "My events",
      description: "Import teams, assign judges, track submissions.",
      icon: Workflow,
    },
    {
      href: "/hackathons/new",
      label: "New hackathon",
      description: "Create an event, set rubrics and scoring weights.",
      icon: Trophy,
      section: "Create",
    },
  ],

  judge: [
    { href: "/home", label: "Home", icon: Home, navOnly: true },
    {
      href: "/evaluations",
      label: "Evaluation queue",
      description: "Submissions assigned to you for scoring.",
      icon: Gavel,
      matchNested: true,
    },
  ],
};

export interface WorkspaceNavSection {
  /** Omitted for the first section, which needs no label above it. */
  label?: string;
  items: RoleCapability[];
}

/** Sidebar shape for a role, derived from `ROLE_CAPABILITIES`.
 *
 * Grouping matters beyond looks: the candidate list is 12 flat items, past the point
 * where a sidebar can be scanned. */
export function navSectionsFor(role: WorkspaceRole): WorkspaceNavSection[] {
  const caps = ROLE_CAPABILITIES[role] ?? ROLE_CAPABILITIES.candidate;
  const ungrouped = caps.filter((c) => !c.section);
  const sections: WorkspaceNavSection[] = ungrouped.length
    ? [{ items: ungrouped }]
    : [];

  for (const label of SECTION_ORDER[role] ?? []) {
    const items = caps.filter((c) => c.section === label);
    if (items.length) sections.push({ label, items });
  }
  return sections;
}

/** Hub-grid entries for a role: everything with a description, minus nav-only items. */
export function hubCapabilitiesFor(role: WorkspaceRole): RoleCapability[] {
  const caps = ROLE_CAPABILITIES[role] ?? ROLE_CAPABILITIES.candidate;
  return caps.filter((c) => !c.navOnly && c.description);
}

/** True when `href` is the nav entry matching the current pathname. Exact by default;
 * prefix-matching only where `matchNested` is set, so /jobs and /jobs/new don't both
 * highlight. */
export function isNavItemActive(
  item: Pick<RoleCapability, "href" | "matchNested">,
  pathname: string,
): boolean {
  if (pathname === item.href) return true;
  return Boolean(item.matchNested) && pathname.startsWith(`${item.href}/`);
}
