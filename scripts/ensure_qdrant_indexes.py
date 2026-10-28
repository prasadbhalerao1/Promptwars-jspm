"""Create the payload indexes every filtered Qdrant search in this app depends on.

The app creates these automatically, but only at the moment it *creates* a collection.
Collections that already existed before payload indexing was added (any dev machine or
deployment seeded earlier) therefore keep running filtered searches unindexed. This
script backfills them; it is idempotent, so re-running is always safe.

Run after `docker compose up -d` / `scripts/seed_db.py`:

    python scripts/ensure_qdrant_indexes.py

Why it matters: a filtered vector search without a payload index on the filtered field
cannot restrict the HNSW traversal to matching points, so cost scales with the size of
the whole collection instead of the matching subset. `candidate_project_embeddings` is
the sharpest case — job matching issues one `candidate_id`-filtered search per candidate
in the pool, so an unindexed payload there multiplies across the entire matching run.
"""

import sys
from pathlib import Path

# Repo root on sys.path so `services` imports when this is run directly as
# `python scripts/ensure_qdrant_indexes.py` — same bootstrap as `scripts/seed_db.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.api.core.qdrant import ensure_payload_indexes, get_qdrant_client  # noqa: E402

# Mirrors the `ensure_payload_indexes(...)` calls at each collection-creation site.
# Keep in sync with:
#   services/agents/recruitment/tools/embeddings.py      (job_description_embeddings)
#   services/agents/candidate_intelligence/tools/judgment_scores.py (candidate_project_embeddings)
#   services/agents/ppt_analyzer/tools/plagiarism.py     (slide_embeddings)
COLLECTION_PAYLOAD_INDEXES: dict[str, dict[str, str]] = {
    "candidate_project_embeddings": {"candidate_id": "keyword"},
    "presentation_slide_embeddings": {"presentation_id": "keyword"},
    "job_description_embeddings": {
        "job_id": "keyword",
        "location": "keyword",
        "remote_ok": "bool",
        "required_skill_tags": "keyword",
    },
}


def main() -> None:
    client = get_qdrant_client(raise_on_unavailable=True)

    for collection, fields in COLLECTION_PAYLOAD_INDEXES.items():
        if not client.collection_exists(collection):
            # Not an error: collections are created lazily on first write, and the
            # creation path indexes them itself.
            print(f"  skip   {collection} (does not exist yet)")
            continue
        ensure_payload_indexes(client, collection, fields)
        schema = client.get_collection(collection).payload_schema or {}
        indexed = ", ".join(sorted(schema)) or "(none)"
        print(f"  ok     {collection}: indexed payload fields -> {indexed}")


if __name__ == "__main__":
    main()
