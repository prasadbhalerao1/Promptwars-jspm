"""Recommended Certifications (FR-4.2) & Learning Recommendations (FR-4.5) — both map
skill gaps to the same curated, statically-seeded `course_catalog` table (doc 01 §8:
"maintained static table ... not scraped live").

Pure function, no DB access here — nodes in this module don't touch the database (same
convention as every other tool in this package); the API route fetches the small,
static catalog once and passes it into graph state as plain dicts.

Doc 01 §5's agent registry routes "course mapping" to Haiku, but this is deliberately
deterministic tag-matching instead of an LLM call: the catalog is a small, fully
curated static table (skills are just tags on ~20 known rows), so a lookup is more
reliable and cheaper than an LLM guess — same "deterministic first" call already made
for `profile_merge.py`'s rule-based conflict detection.
"""


def match_courses(catalog: list[dict], gap_skills: list[str], limit_per_skill: int = 2) -> list[dict]:
    if not gap_skills or not catalog:
        return []

    wanted = [s.lower() for s in gap_skills]
    matched: dict[str, dict] = {}
    counts: dict[str, int] = {}

    # Walk gap_skills in priority order so higher-priority gaps get their course slots
    # filled first when multiple gaps compete for the same `limit_per_skill` courses.
    for skill in wanted:
        for entry in catalog:
            if counts.get(skill, 0) >= limit_per_skill:
                break
            tags = {t.lower() for t in (entry.get("skill_tags") or [])}
            if skill not in tags:
                continue
            entry_id = entry["id"]
            if entry_id in matched:
                continue
            matched[entry_id] = entry
            counts[skill] = counts.get(skill, 0) + 1

    return list(matched.values())
