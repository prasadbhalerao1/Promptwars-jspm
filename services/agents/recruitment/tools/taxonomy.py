"""Skill/location synonym resolution for the Query Understanding Agent (FR-3.1/3.2).
Reads the `skill_taxonomy`/`location_aliases` tables — plain dict lookups, no LLM, no
Qdrant. Nodes never touch the DB directly (candidate_intelligence convention); the router
fetches these rows once per request and passes them into state as plain dicts.
"""


def resolve_skill(raw_skill: str, skill_synonyms: dict[str, list[str]]) -> str:
    """Maps a raw skill token (however the query-understanding LLM extracted it) to its
    canonical name, e.g. "ML" / "machine learning" -> "machine learning". Falls back to
    the lowercased raw token when there's no taxonomy entry — an unrecognized skill is
    still searched literally, never dropped."""
    normalized = raw_skill.strip().lower()
    for canonical, synonyms in skill_synonyms.items():
        if normalized == canonical.lower() or normalized in (s.lower() for s in synonyms):
            return canonical
    return normalized


def resolve_location(raw_location: str, location_aliases: dict[str, list[str]]) -> str:
    normalized = raw_location.strip().lower()
    for canonical, aliases in location_aliases.items():
        if normalized == canonical.lower() or normalized in (a.lower() for a in aliases):
            return canonical
    return raw_location.strip()
