# TRACE: Platform Documentation

This directory contains the complete technical documentation for the TRACE AI hiring and
hackathon platform, organized by module. Each doc is written as if explaining the system in
a technical interview: confident, precise, focused on *why* decisions were made, and honest
about what's unfinished or scoped out.

## Documentation files

0. **[00-architecture-overview.md](00-architecture-overview.md)** — Start here. System
   diagram, full tech stack, repo structure, agent/database inventories, and an honest
   statement of current deployment status (local dev only, no committed deploy manifest).

1. **[01-authentication-and-rbac.md](01-authentication-and-rbac.md)** — Custom
   email+password auth, JWT issuance/verification, server-side role enforcement via
   `require_role`, and the in-memory rate limiter.

2. **[02-candidate-intelligence-and-talent-score.md](02-candidate-intelligence-and-talent-score.md)** —
   The AI Talent Profile Engine and the 9-dimensional Talent Score: resume parsing, GitHub
   analysis, certificate OCR, cold-start-safe scoring, and job-contextual score adjustment.

3. **[03-resume-portfolio-and-career-guidance.md](03-resume-portfolio-and-career-guidance.md)** —
   Resume/cover-letter generation with a fact-check guardrail, public portfolio pages, and
   career guidance (skill gaps, salary prediction, learning paths).

4. **[04-recruitment-matching-and-copilot.md](04-recruitment-matching-and-copilot.md)** —
   The job-matching formula (skill overlap, semantic similarity, experience, Talent Score)
   and the natural-language Recruiter Copilot.

5. **[05-skill-verification-and-assessments.md](05-skill-verification-and-assessments.md)** —
   Coding assessments, MCQ tests, project analysis, and hackathon team contribution
   attribution via git commit analysis.

6. **[06-ai-interview-agent.md](06-ai-interview-agent.md)** — Turn-based, conditionally
   routed AI interviews with live scoring and a structured final report.

7. **[07-ppt-pitch-deck-analyzer.md](07-ppt-pitch-deck-analyzer.md)** — Pitch deck rubric
   scoring, plagiarism/novelty detection, and background-task-based analysis.

8. **[08-hackathon-to-hiring-pipeline.md](08-hackathon-to-hiring-pipeline.md)** — Team
   ranking (judge + pitch + repo + novelty), and event-driven, live-computed recruiter
   matching against hackathon top performers.

9. **[09-trust-and-fraud-prevention.md](09-trust-and-fraud-prevention.md)** — The platform's
   most detailed module: certificate verification, plagiarism detection, duplicate profile
   detection, AI-content signals, the trusted issuer registry, and the core "flags never
   auto-affect scoring" principle.

10. **[10-multi-agent-architecture.md](10-multi-agent-architecture.md)** — The 12-graph,
    7-module LangGraph architecture; the supervisor's real (deliberately partial) scope; the
    DB-free node convention; a worked conditional-routing example.

11. **[11-vector-search-and-llm-gateway.md](11-vector-search-and-llm-gateway.md)** — The
    shared AI infrastructure: Qdrant collections, the bare-vs-described skill embedding
    discovery, the multi-provider LLM gateway, failure modes, and performance
    characteristics.

12. **[12-ui-design-system.md](12-ui-design-system.md)** — Design philosophy and the actual
    frontend library stack (Tailwind 4, shadcn, framer-motion, recharts, @dnd-kit,
    @monaco-editor/react).

13. **[13-role-flows-and-use-cases.md](13-role-flows-and-use-cases.md)** — Plain-English
    step-by-step flows and use cases for each of the five roles: Candidate, Recruiter,
    Organizer, Judge, Admin.

14. **[14-prompts-architecture.md](14-prompts-architecture.md)** — The markdown-based prompt
    system: per-module `prompts/` directories, the `load_prompt()` loader, and how to add a
    new prompt.

15. **[15-local-development-setup.md](15-local-development-setup.md)** — How to actually run
    this locally: `dev-up.ps1`, service URLs, infrastructure (Postgres/Redis/Qdrant), and
    secrets setup for every real integration (Anthropic, GitHub OAuth, Cloudinary, Langfuse,
    Sentry).

## Key architectural insights

### The "bare skill name vs described embedding" discovery
Bare embeddings ("Vue.js" embed ≈ "Photoshop" embed when compared to React) are ambiguous.
Adding one-sentence descriptions per skill ("Vue.js: progressive JS framework...") fixes
this to 0.89 (Vue/React) vs 0.66 (Photoshop/React) — measured and tuned. Used across job
matching, skill gap analysis, and hard-filter fallback. See doc 11.

### Cold-start renormalization pattern
Used across Talent Score, Pitch Score, Hackathon Ranking, Job Matching, and Coding Ability.
When a component is missing, drop it and renormalize remaining weights to sum to 1.0. Never
fabricate a 0.0. Consolidated into one shared `weighted_renormalized_mean()` helper. See
docs 02, 08, and 11.

### Fraud engine's "flags never auto-affect" principle
Raised flags have zero impact on scoring or visibility. Only human-upheld flags (with
non-null review notes and evidence) contribute penalties — enforced at the database layer
(`NOT NULL` constraints), not just code convention. See doc 09.

### Event-driven recruiter matching (not pre-computed)
Hackathon rankings finalize → an event is published. When a recruiter later creates a
watchlist, they're polled against the event and matched live at poll time, not from a
pre-computed table — this catches recruiters who add a watchlist after the event finalized.
Tradeoff: ~5 second polling latency vs. correctness. See doc 08.

### Background tasks for long-running AI analysis
Pitch deck analysis and candidate ingestion used to block HTTP requests for 15–40+ seconds
with no progress feedback. Both now run as FastAPI `BackgroundTasks`, returning immediately
with a `processing` status while the frontend polls for completion. See docs 02 and 07. (Note:
this is in-process background work, not a distributed task queue — see doc 00's "Task queue"
note for the honest scope of what's actually running.)

## How to read this documentation

**For understanding the full system**: Start with doc 00 (Architecture Overview) for the
big picture, then doc 10 (Multi-Agent Architecture) for the orchestration model, then doc 09
(Trust & Fraud Prevention) for the most detailed single module.

**For a specific feature**: Use the table of contents above to jump straight to the module
you care about.

**For implementation details**: Each doc includes file paths and line numbers. Use them to
navigate the actual codebase.

**For architectural decisions**: Every "Key design decisions" section explains trade-offs,
constraints, and honest limitations — including where something is a deliberate scope
choice rather than an unfinished feature.

## Document status

- 16 files total: this README plus 00 through 15.
- All auth-related content reflects the current custom email+password/JWT system — no
  references to any third-party identity provider in the live auth path.
- All file:line references were checked against the current codebase at the time of writing.

---

**Last updated**: August 2, 2026
