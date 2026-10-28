"""Target-role skill taxonomy — FR-4.1's "embedded requirement sets of target roles."

A curated, hand-maintained catalog (same "seed a static table, don't scrape live"
philosophy as the course catalog in doc 01 §8) rather than pulled from any live job-
board API. Each role maps to `(skill_name, weight)` pairs; weight (0-1) is how
important that skill is to the role, used to break ties when ranking gaps.

The authoritative copy now lives in the `role_skill_requirements` table — adding a role
is a DB insert, not a code change and redeploy, which is what the "curated catalog"
philosophy above always implied but this module could not deliver while it was a dict
literal. `skill_gap.py` still seeds Qdrant from whatever this resolves to, idempotently.

The literal below is the SEED: it is what `scripts/seed_db.py` inserts on a fresh
database, and what `services/agents/catalogs.py` falls back to if the database is
unreachable or the catalog migration has not been applied yet. Read the catalog through
`ROLE_SKILL_TAXONOMY` (below), never through the seed directly.
"""

ROLE_SKILL_TAXONOMY_SEED: dict[str, list[tuple[str, float]]] = {
    "Backend Engineer": [
        ("python", 0.9),
        ("sql", 0.9),
        ("rest api design", 0.85),
        ("docker", 0.7),
        ("postgresql", 0.75),
        ("system design", 0.8),
        ("git", 0.6),
        ("caching", 0.6),
        ("message queues", 0.55),
        ("unit testing", 0.6),
    ],
    "Frontend Engineer": [
        ("javascript", 0.9),
        ("typescript", 0.8),
        ("react", 0.9),
        ("css", 0.75),
        ("html", 0.6),
        ("accessibility", 0.55),
        ("web performance", 0.6),
        ("state management", 0.65),
        ("testing library", 0.5),
        ("git", 0.5),
    ],
    "Full-Stack Engineer": [
        ("javascript", 0.85),
        ("python", 0.7),
        ("react", 0.8),
        ("sql", 0.75),
        ("rest api design", 0.8),
        ("docker", 0.6),
        ("system design", 0.7),
        ("git", 0.55),
        ("typescript", 0.6),
        ("ci/cd", 0.55),
    ],
    "Data Scientist": [
        ("python", 0.9),
        ("pandas", 0.85),
        ("machine learning", 0.9),
        ("statistics", 0.85),
        ("sql", 0.75),
        ("data visualization", 0.65),
        ("scikit-learn", 0.7),
        ("experiment design", 0.6),
        ("jupyter", 0.5),
        ("communication", 0.55),
    ],
    "Machine Learning Engineer": [
        ("python", 0.9),
        ("machine learning", 0.9),
        ("pytorch", 0.8),
        ("mlops", 0.75),
        ("docker", 0.65),
        ("sql", 0.6),
        ("distributed systems", 0.6),
        ("model evaluation", 0.7),
        ("feature engineering", 0.65),
        ("cloud computing", 0.6),
    ],
    "DevOps Engineer": [
        ("docker", 0.9),
        ("kubernetes", 0.9),
        ("ci/cd", 0.85),
        ("terraform", 0.75),
        ("aws", 0.8),
        ("linux", 0.8),
        ("bash scripting", 0.65),
        ("monitoring", 0.7),
        ("networking", 0.55),
        ("python", 0.5),
    ],
    "Mobile Engineer": [
        ("kotlin", 0.7),
        ("swift", 0.7),
        ("react native", 0.75),
        ("mobile ui design", 0.65),
        ("rest api design", 0.6),
        ("app performance", 0.6),
        ("git", 0.5),
        ("testing", 0.55),
        ("push notifications", 0.4),
        ("offline storage", 0.5),
    ],
    "Cloud/Platform Engineer": [
        ("aws", 0.85),
        ("kubernetes", 0.8),
        ("terraform", 0.8),
        ("networking", 0.7),
        ("security fundamentals", 0.65),
        ("docker", 0.7),
        ("linux", 0.7),
        ("cost optimization", 0.5),
        ("monitoring", 0.6),
        ("python", 0.5),
    ],
    "Site Reliability Engineer": [
        ("kubernetes", 0.85),
        ("monitoring", 0.85),
        ("incident response", 0.8),
        ("linux", 0.75),
        ("python", 0.6),
        ("networking", 0.6),
        ("terraform", 0.6),
        ("ci/cd", 0.6),
        ("distributed systems", 0.65),
        ("bash scripting", 0.55),
    ],
    "Security Engineer": [
        ("security fundamentals", 0.9),
        ("penetration testing", 0.75),
        ("networking", 0.75),
        ("cryptography", 0.65),
        ("incident response", 0.7),
        ("linux", 0.6),
        ("python", 0.55),
        ("cloud security", 0.65),
        ("threat modeling", 0.6),
        ("compliance", 0.5),
    ],
}


class _RoleSkillTaxonomy(dict):
    """Mapping view that resolves from the database on each construction.

    Subclasses `dict` so every existing consumer keeps working untouched — this catalog
    is indexed, iterated, `in`-tested, passed to `sorted()` and used as a `max()` key
    across `skill_gap.py` and `candidates/router.py`. Rebuilding on access (behind
    `catalogs.py`'s TTL cache, so a rebuild is a dict copy rather than a query) means an
    admin edit takes effect without a restart.
    """

    def __init__(self) -> None:
        from services.agents.catalogs import role_skill_taxonomy

        super().__init__(role_skill_taxonomy())


def get_role_skill_taxonomy() -> dict[str, list[tuple[str, float]]]:
    """Current role requirement sets, from the database (falling back to the seed)."""
    return _RoleSkillTaxonomy()


ROLE_SKILL_TAXONOMY = _RoleSkillTaxonomy()
