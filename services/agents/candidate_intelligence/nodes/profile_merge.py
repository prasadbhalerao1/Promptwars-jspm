"""Profile Merge Agent — doc 01 §4. Rule-based merge + conflict detection.

Deterministic merge first, per doc 01's own agent registry note — no LLM call needed
for this node in this slice; the doc's "LLM conflict summary" refinement is left for a
follow-up once the mechanical merge/conflict-flagging path is proven out.

Returns only the keys it changes (see resume_parser.py's note on why) — `conflicts`
here must be only the NEW entries this node discovers, since `conflicts` is a
reducer-backed channel (operator.add) that already holds whatever resume_parser/
certificate_ocr contributed in the prior superstep.
"""

from services.agents.candidate_intelligence.state import CandidateProfileState


def _resume_years_experience(resume_parsed: dict) -> float:
    return sum(e.get("years") or 0 for e in resume_parsed.get("experience", []))


def _github_active_years(github_raw) -> float:
    if github_raw is None or not github_raw.commit_activity_weekly:
        return 0.0
    active_weeks = sum(1 for c in github_raw.commit_activity_weekly if c > 0)
    return round(active_weeks / 52, 1)


async def run(state: CandidateProfileState) -> dict:
    resume = state.get("resume_parsed") or {}
    github_raw = state.get("github_raw")

    new_conflicts: list[str] = []

    if resume and github_raw is not None:
        resume_years = _resume_years_experience(resume)
        github_years = _github_active_years(github_raw)
        # Doc 01 §3 FR-1.5 worked example: resume says N years, GitHub shows far less
        # activity — flag rather than silently trusting either source.
        if resume_years >= 2 and github_years > 0 and resume_years > github_years * 2:
            new_conflicts.append(
                f"experience_mismatch: resume claims {resume_years:.0f}y, "
                f"GitHub shows ~{github_years:.0f}y of active-commit history"
            )

    all_conflicts = [*state.get("conflicts", []), *new_conflicts]

    merged = {
        "github_username": state.get("github_username"),
        "headline": resume.get("headline"),
        "location": resume.get("location"),
        "skills": resume.get("skills", []),
        "experience": resume.get("experience", []),
        "education": resume.get("education", []),
        "merged_conflicts": [{"description": c, "resolved": False} for c in all_conflicts],
    }

    return {"merged_profile": merged, "conflicts": new_conflicts}
