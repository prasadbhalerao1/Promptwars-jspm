"""Badge Assignment Agent — doc 01 §3 FR-3.5. Rules only, no LLM (doc 01 §4)."""

from services.agents.candidate_intelligence.state import CandidateProfileState


async def run(state: CandidateProfileState) -> dict:
    merged = state.get("merged_profile") or {}
    github_raw = state.get("github_raw")

    skill_names = {s.get("name", "").strip().lower() for s in merged.get("skills", []) if s.get("name")}
    github_languages: set[str] = set()
    if github_raw is not None:
        for repo in github_raw.repos:
            github_languages.update(lang.lower() for lang in repo.languages)

    badges = []
    for skill in skill_names:
        sources = ["resume"]
        if skill in github_languages:
            sources.append("github")
        if len(sources) >= 2:
            badges.append({"skill_name": skill, "corroboration_sources": sources})

    return {"badges": badges}
