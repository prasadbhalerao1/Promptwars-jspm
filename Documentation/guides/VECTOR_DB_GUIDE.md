# Vector Database (Qdrant) Architecture Guide

**Updated:** 2026-08-01  
**Scope:** Complete vector DB integration across all modules  
**Dependencies:** Qdrant (local Docker), `sentence-transformers` (BAAI/bge-large-en-v1.5)

---

## Overview

Qdrant is a **semantic search engine** storing vector embeddings of:
- **Job Descriptions** — for skill/role matching
- **Candidate Projects** — for relevance scoring
- **Skill Taxonomy** — for gap analysis
- **PPT Slide Content** — for plagiarism/novelty detection

**Why Vectors?** Match concepts (not keywords):
- Candidate has "Vue.js" → Job requires "React" → **Similarity: 0.89** (siblings, partial credit)
- Candidate has "Photoshop" → Job requires "React" → **Similarity: 0.66** (unrelated, no credit)
- Free-text query "senior full-stack engineer" → Search across skill centroids

---

## Collections & Data Model

### 1. **`job_description_embeddings`** (Recruitment Module)

**Purpose:** Store job postings as 384-dim vectors for semantic matching

**Schema:**
```python
PointStruct(
  id=uuid5("job:{job_id}"),           # Deterministic, idempotent
  vector=[float] * 384,                # Embedding from JD text
  payload={
    "job_id": str,                     # Reference to job row
    "location": str | null,            # "San Francisco, CA"
    "remote_ok": bool,                 # Hard filter
    "required_skill_tags": [str],      # ["Python", "React", ...]
  }
)
```

**Populated by:** `services/agents/recruitment/nodes/job_embed.py`  
**Created:** When recruiter creates a job definition  
**Upserted:** `embeddings.upsert_job_embedding()`

**Vector Source:**
```python
job_text = f"{job.title} {job.description} {' '.join(job.required_skills)}"
job_vector = embed_texts([job_text])[0]  # → [384 floats]
```

**Distance Metric:** COSINE (similarity, not distance)

---

### 2. **`candidate_project_embeddings`** (Candidate Intelligence Module)

**Purpose:** Store candidate's GitHub projects for relevance scoring

**Schema:**
```python
PointStruct(
  id=uuid5("project:{candidate_id}:{repo_name}"),
  vector=[float] * 384,                # Embedding from project description
  payload={
    "candidate_id": str,               # Reference to candidate
    "repo_name": str,                  # "{full_name}: {languages}"
                                       # e.g., "user/ml-pipeline: Python, Jupyter"
  }
)
```

**Populated by:** `services/agents/candidate_intelligence/tools/judgment_scores.py`  
**Created:** During initial GitHub profile analysis  
**Updated:** When candidate's GitHub is re-scraped

**Vector Source:**
```python
# Create one point per project (top 10 most recent)
for repo in candidate.repos[:10]:
  desc = f"{repo.name}: {repo.languages}. {repo.description}"
  vector = embed_texts([desc])[0]
  upsert_point(candidate_id, repo.full_name, vector)
```

**Queried by:**
- `matching.py:candidate_project_relevance()` — 0-100 similarity score
- `recruitment/copilot` — free-text semantic search
- `project_relevance.py` — talent score sub-component

---

### 3. **`skill_taxonomy_embeddings`** (Career Guidance Module)

**Purpose:** Embed skill taxonomy for gap analysis (which skills is candidate missing?)

**Schema:**
```python
PointStruct(
  id=uuid5("role:skill"),              # e.g., uuid5("Backend Engineer:Python")
  vector=[float] * 384,                # Embedding from skill description
  payload={
    "role": str,                       # "Backend Engineer", "Frontend Engineer"
    "skill": str,                      # "Python", "React", etc.
    "weight": float,                   # 1.0 = critical, 0.5 = nice-to-have
  }
)
```

**Populated by:** `services/agents/candidate_intelligence/tools/skill_gap.py:_ensure_seeded()`  
**Creation:** Idempotent on first request (upsert via uuid5)

**Vector Source:**
```python
# Uses curated skill descriptions, NOT bare skill names
# Bare "React" embeds too close to "Vue.js" (0.65)
# With descriptions: "React is a JS library..." vs "Vue.js is a JS library..." = 0.89
for role, skills in ROLE_SKILL_TAXONOMY.items():
  for skill_name, weight in skills:
    desc = describe_skill(skill_name)  # → "React is a JavaScript library..."
    vector = embed_texts([desc])[0]
    upsert_point(role, skill_name, weight, vector)
```

**Similarity Threshold:** `0.72` (gap detection cutoff)

---

### 4. **PPT Analyzer Embeddings** (Pitch Deck Analysis)

**Purpose:** Embed each slide's text for cross-event novelty & plagiarism detection

**Schema:** Ad-hoc, not stored in Qdrant permanently
```python
# Computed in-memory during analysis
slide_embeddings = [
  embed_texts(f"{slide.title} {slide.body} {slide.notes}")[0]
  for slide in presentation.slides
]
```

**Used for:**
- Cross-event novelty: Compare candidate's slides vs. past submissions
- Plagiarism detection: Cosine similarity check

---

## Query Patterns & Thresholds

### Pattern 1: Job Matching (FR-2)

**Query:**
```python
# During recruiter → candidate matching
job_vector = job_embeddings[job_id]
hits = client.search(
  "candidate_project_embeddings",
  query_vector=job_vector,
  query_filter=Filter(
    must=[FieldCondition("candidate_id", match=candidate_id)]
  ),
  limit=10,
)
```

**Score Calculation:**
```
project_relevance = mean([h.score for h in hits]) * 100
# Returns 0-100, or None if no projects found

Example: 10 projects, avg similarity 0.75 → 75/100 relevance
```

**Used in:** `matching.py:semantic_similarity()` → 30% of total match score

---

### Pattern 2: Skill Filtering (Copilot)

**Query:** Hard filter for skills, then semantic rank for free-text

```python
# Step 1: Filter candidates by exact/similar skill match
for required_skill in job_skills:
  required_vector = embed_texts([describe_skill(required_skill)])[0]
  candidate_matches = all(
    candidate_has_skill(candidate_skill) 
    or cosine_similarity(required_vector, candidate_vector) >= 0.80
    for candidate_skill in candidate.skills
  )
```

**Threshold:** `SKILL_SIMILARITY_THRESHOLD = 0.80`  
(Tuned to separate "React" vs "Vue" (0.89) from "React" vs "Photoshop" (0.66))

---

### Pattern 3: Free-Text Semantic Search

**Query:** Copilot search for "senior full-stack engineer"

```python
semantic_query = "senior full-stack engineer with AI experience"
query_vector = embed_texts([semantic_query])[0]

for candidate in shortlist:
  centroid = candidate_skill_centroid(candidate.skill_names)
  similarity = cosine_similarity(query_vector, centroid)
  match_percentage = round(100 * similarity, 1)
```

**Centroid:** Average of candidate's skill vectors
- Captures overall profile without summing individual embeddings
- Single query-to-centroid comparison is O(384), not O(384 × num_skills)

---

### Pattern 4: Skill Gap Analysis (Career Guidance)

**Query:** Find which skills candidate is missing for target role

```python
# Embed candidate's existing skills
candidate_vectors = embed_texts([describe_skill(s) for s in candidate.skills])
candidate_centroid = mean(candidate_vectors)

# Compare against role's skill requirements
role_skills = ROLE_SKILL_TAXONOMY["Backend Engineer"]
for skill, weight in role_skills:
  skill_vector = retrieve_from_qdrant("skill_taxonomy_embeddings", skill)
  similarity = cosine_similarity(candidate_centroid, skill_vector)
  
  if similarity < 0.72:  # Below threshold
    gaps.append({
      "skill": skill,
      "similarity": similarity,
      "priority": weight,
    })
```

**Output:** Sorted list (biggest gaps first)

---

## Embedding Model

**Model:** `BAAI/bge-large-en-v1.5`  
**Dimensions:** 384 (compact, vs 1536 for OpenAI)  
**Cost:** Free (open-source), runs on-device  
**Latency:** ~50ms per 100 texts on CPU, <5ms on GPU

**Caching:** Process-level singleton via `@functools.lru_cache(maxsize=1)`
```python
@functools.lru_cache(maxsize=1)
def get_embedder():
  from sentence_transformers import SentenceTransformer
  return SentenceTransformer("BAAI/bge-large-en-v1.5")

# Load once per process, reuse across all requests
```

**Why cached?** Model loading from disk is ~3 seconds; without cache, every request (job creation, matching, Copilot search) reloads it and compounds badly.

---

## Failure Modes & Graceful Degradation

### Hard Failures (503 if Qdrant unavailable)

Raised as `QdrantUnavailable` → propagates to caller as HTTP 503:

1. **Recruitment Matching** — Cannot compute semantic_similarity → cannot rank candidates
2. **Skill Gap Analysis** — Cannot find gaps → cannot give career guidance

**Principle:** Better to fail explicitly than rank wrong.

### Soft Failures (cold-start, `None` returned)

Gracefully skip embeddings if Qdrant unavailable, rely on other signals:

1. **Innovation Novelty** — One signal among several; Qdrant down → use GitHub metrics only
2. **Plagiarism Detection** — One signal; Qdrant down → use text fingerprinting only
3. **Project Relevance** — Returns `None` if candidate has no projects → re-normalized away

**Pattern:**
```python
try:
  client = get_qdrant_client(raise_on_unavailable=False)  # Returns None, not exception
  if client:
    relevance = candidate_project_relevance(client, candidate_id, job_vector)
  else:
    relevance = None  # Skip, don't zero
except QdrantUnavailable:
  relevance = None

# Re-normalize: if relevance is None, its weight gets redistributed
```

---

## Performance Characteristics

| Operation | Latency | Notes |
|-----------|---------|-------|
| `embed_texts()` (1 item) | ~1ms | Cached model, single CPU |
| `search()` (1 query) | ~10ms | HNSW index, loopback round trip |
| `search_batch()` (100 queries) | ~50ms | One round-trip, not 100×10ms |
| `upsert()` (1 point) | ~20ms | Immediate index update |
| Skill centroid (10 skills) | ~5ms | NumPy mean, no Qdrant call |

**Optimization Applied:**
```python
# ❌ SLOW: 100 candidates × 10ms = 1 second
for candidate in candidates:
  relevance = candidate_project_relevance(client, candidate_id, job_vector)

# ✅ FAST: 100 candidates in one batch = 50ms
batch_relevance = batch_candidate_project_relevance(
  client, [c.id for c in candidates], job_vector
)
```

---

## Qdrant Configuration

**Deployment:** Local Docker container (`trace_qdrant`, `infra/docker-compose.yml`)  
**URL:** `http://localhost:6333` — set as `QDRANT_URL` in `.env`  
**API Key:** none needed locally; `QDRANT_API_KEY` is blank  
**Data:** persists in the `qdrantdata` Docker volume  
**Timeout:** 5 seconds (connection + first query)

**Collections Auto-Created:**
- On first upsert, if collection doesn't exist
- Vector size inferred from first point
- Distance metric: COSINE (not L2/Manhattan)

---

## Monitoring & Debugging

### Check Qdrant Health
```bash
curl http://localhost:6333/healthz
```
Or open the dashboard at http://localhost:6333/dashboard.

### List Collections
```bash
python -c "
from services.api.core.qdrant import get_qdrant_client
client = get_qdrant_client()
print([c.name for c in client.get_collections().collections])
"
```

### Count Points in Collection
```bash
python -c "
from services.api.core.qdrant import get_qdrant_client
client = get_qdrant_client()
count = client.count('job_description_embeddings').count
print(f'Job embeddings: {count}')
"
```

### Debug a Semantic Query
```python
from services.agents.recruitment.tools.embeddings import embed_texts, cosine_similarity
from services.agents.recruitment.tools.skill_descriptions import describe_skill

query = "senior Python backend engineer"
query_vec = embed_texts([query])[0]

skill = "Python"
skill_vec = embed_texts([describe_skill(skill)])[0]

sim = cosine_similarity(query_vec, skill_vec)
print(f"Similarity('{query}', '{skill}'): {sim:.3f}")
```

---

## Key Design Decisions

### 1. Skill Descriptions, Not Bare Names

**Decision:** Embed curated descriptions (e.g., "React is a JavaScript library..."), not bare skill names.

**Why:** Bare names don't separate siblings from unrelated skills reliably:
- "React" vs "Vue.js" (bare): 0.65 similarity
- "React" vs "Vue.js" (described): 0.89 similarity ← clear match
- "React" vs "Photoshop" (described): 0.66 similarity ← clear non-match

**Source:** `services/agents/recruitment/tools/skill_descriptions.py` (manual curation)

---

### 2. Candidate Skill Centroid for Free-Text Search

**Decision:** Use mean of candidate's skill embeddings, not Qdrant search on `candidate_project_embeddings`.

**Why:**
- Simpler: no Qdrant query per candidate needed
- Faster: one NumPy mean vs. one search round-trip
- Captures overall profile without over-weighting any single project
- Still works for candidates with no seeded project embeddings

---

### 3. Deterministic UUIDs for Idempotent Upserts

**Decision:** Use `uuid5(namespace, seed_string)` for point IDs.

**Why:**
- Running re-seed twice doesn't duplicate points
- Allows safe re-runs of data pipelines
- Job ID → same UUID every time

```python
id = uuid5(NAMESPACE_URL, f"job:{job_id}")
# Always same UUID for job "12345", safe to upsert repeatedly
```

---

### 4. Payload Filters for Candidate Isolation

**Decision:** Query with `query_filter` matching candidate_id, not full scan + Python filter.

**Why:** Qdrant's HNSW index skips non-matching points, 10x faster than fetch-all + filter.

```python
# ✅ FAST: Qdrant does the filtering
hits = client.search(
  collection,
  query_vector=vector,
  query_filter=Filter(must=[FieldCondition("candidate_id", match=candidate_id)]),
  limit=10,
)

# ❌ SLOW: Fetch all, filter in Python
all_hits = client.search(collection, query_vector=vector, limit=10000)
filtered = [h for h in all_hits if h.payload["candidate_id"] == candidate_id]
```

---

## Future Enhancements

1. **Fine-tuned embeddings** — Currently BAAI/bge generic; could fine-tune on TRACE's domain
2. **Sparse-dense hybrid** — Combine BM25 (keyword) + HNSW (semantic) for robustness
3. **Embedding versioning** — Track which model generated which vector; re-embed on model upgrade
4. **Re-seeding script** — Batch refresh all job/candidate embeddings without downtime

---

## References

- **Qdrant Docs:** https://qdrant.tech/documentation/
- **Sentence Transformers:** https://www.sbert.net/
- **TRACE SRS 01 §7:** Career Guidance skill gap specification
- **TRACE Doc 02:** Recruitment module vector search patterns
- **TRACE Doc 08 §2:** Match score formula (embedding weights)
