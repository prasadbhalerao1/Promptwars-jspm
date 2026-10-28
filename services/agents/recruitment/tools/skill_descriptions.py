"""Curated skill-description taxonomy for embedding-based skill similarity.

Bare skill names (e.g. "Vue.js", "React") don't carry enough semantic content for a
general-purpose sentence embedder to separate genuinely related skills from unrelated
ones — measured directly: "Vue.js" vs "React" embeds at 0.65 cosine similarity, almost
identical to "Photoshop" vs "React" at 0.64, because there's no context for the model to
work with. Adding one descriptive sentence per skill fixes this cleanly: the same
comparison with descriptions jumps to 0.89 (Vue.js/React) vs 0.66 (Photoshop/React) — a
wide, reliable gap. This is the same "seed a static table, don't scrape live" philosophy
as `candidate_intelligence/tools/role_taxonomy.py`, applied to skill-to-skill similarity
instead of role-to-skill requirements.

Hand-maintained and intentionally small — extend as new skills come up in job postings
or candidate profiles rather than trying to enumerate every possible skill up front. A
skill with no entry here just falls back to its bare name (still better than nothing,
per `embeddings.py::skill_description_or_name`).
"""

SKILL_DESCRIPTIONS_SEED: dict[str, str] = {
    "react": "React: a JavaScript library for building user interfaces with reusable components",
    "vue.js": "Vue.js: a progressive JavaScript frontend framework for building user interfaces, similar in purpose to React and Angular",
    "vue": "Vue.js: a progressive JavaScript frontend framework for building user interfaces, similar in purpose to React and Angular",
    "angular": "Angular: a TypeScript-based frontend framework for building single-page web applications, similar in purpose to React and Vue",
    "svelte": "Svelte: a compiler-based JavaScript frontend framework for building user interfaces, similar in purpose to React and Vue",
    "next.js": "Next.js: a React framework for server-rendered and statically generated web applications",
    "nuxt": "Nuxt: a Vue.js framework for server-rendered and statically generated web applications",
    "django": "Django: a Python web framework for building server-side web applications and REST APIs",
    "flask": "Flask: a lightweight Python web framework for building server-side web applications and REST APIs",
    "fastapi": "FastAPI: a modern Python web framework for building REST APIs with async support",
    "express": "Express: a Node.js web framework for building server-side web applications and REST APIs",
    "nestjs": "NestJS: a TypeScript Node.js framework for building server-side web applications and REST APIs",
    "spring boot": "Spring Boot: a Java framework for building server-side web applications and REST APIs",
    "ruby on rails": "Ruby on Rails: a Ruby web framework for building server-side web applications",
    "postgresql": "PostgreSQL: a relational SQL database management system",
    "mysql": "MySQL: a relational SQL database management system",
    "sqlite": "SQLite: a lightweight embedded relational SQL database",
    "mongodb": "MongoDB: a document-oriented NoSQL database",
    "redis": "Redis: an in-memory key-value data store used for caching and message queues",
    "elasticsearch": "Elasticsearch: a distributed search and analytics engine",
    "docker": "Docker: a containerization platform for packaging and running applications",
    "kubernetes": "Kubernetes: a container orchestration platform for deploying and scaling containerized applications",
    "terraform": "Terraform: an infrastructure-as-code tool for provisioning cloud resources",
    "aws": "AWS (Amazon Web Services): a cloud computing platform providing compute, storage, and managed services",
    "gcp": "Google Cloud Platform: a cloud computing platform providing compute, storage, and managed services",
    "azure": "Microsoft Azure: a cloud computing platform providing compute, storage, and managed services",
    "python": "Python: a general-purpose, high-level programming language commonly used for backend development, data science, and automation",
    "javascript": "JavaScript: a programming language used for web frontend and backend (Node.js) development",
    "typescript": "TypeScript: a statically-typed superset of JavaScript used for frontend and backend development",
    "java": "Java: a general-purpose, statically-typed programming language commonly used for backend and enterprise applications",
    "go": "Go (Golang): a statically-typed, compiled programming language commonly used for backend services and infrastructure tooling",
    "rust": "Rust: a statically-typed, memory-safe systems programming language",
    "c++": "C++: a general-purpose, compiled systems programming language",
    "tensorflow": "TensorFlow: a machine learning framework for building and training neural networks",
    "pytorch": "PyTorch: a machine learning framework for building and training neural networks",
    "scikit-learn": "scikit-learn: a Python machine learning library for classical (non-deep-learning) models",
    "pandas": "pandas: a Python data manipulation and analysis library",
    "figma": "Figma: a collaborative interface design and prototyping tool",
    "photoshop": "Adobe Photoshop: raster graphics editing software for photo editing and digital design",
}


def describe_skill(skill_name: str) -> str:
    """Returns the curated description for a skill, or the bare name if uncatalogued —
    an unrecognized skill still gets compared, just with less semantic signal, rather
    than being dropped or erroring."""
    # Resolved from the `skill_descriptions` table (via catalogs.py's cache), falling
    # back to the seed below when the database is unreachable. Unknown skills return
    # their own name, which is a usable — if less semantically rich — embedding input.
    from services.agents.catalogs import skill_descriptions

    return skill_descriptions().get(skill_name.strip().lower(), skill_name)


# Backwards-compatible alias: the seed is the fallback, not the source of truth. Prefer
# `skill_text()` above, which reads the database.
SKILL_DESCRIPTIONS = SKILL_DESCRIPTIONS_SEED
