# Recruitment: Job Matching Engine & AI Copilot

## What it does

**Job Matching**: Ranks candidates against a job posting using a 4-term weighted formula combining skill overlap, semantic similarity, experience alignment, and talent score.

**Recruiter Copilot**: Natural language assistant that lets recruiters query candidates with phrases like "Find backend engineers in NYC with Python and React experience who scored 75+".

## How Job Matching works

```
Job Posting (required skills, level, seniority)
    ↓
    ├─→ Candidate Pool (all verified profiles)
    │
    ├─→ For each candidate:
    │   ├─ skill_overlap: Match required skills against profile
    │   ├─ semantic_similarity: Embed candidate/job → Qdrant cosine
    │   ├─ experience_match: Years in role vs. job level
    │   └─ talent_score_alignment: Candidate's Talent Score vs. job expectations
    │
    └─→ Weighted renormalization:
           score = (0.30 * skill + 0.25 * semantic + 0.25 * exp + 0.20 * talent) / sum(weights)
           (missing terms dropped, weights renormalized)
```

**Key Fix**: Skill matching now uses embedding-based similarity (not just exact string match).
- "Vue.js" candidate vs "React" job: 0.53 partial credit (related frameworks)
- "Photoshop" candidate vs "React" job: 0 (unrelated)
- Uses curated skill descriptions: "Vue.js: progressive JS framework similar to React..."

**Key Code**:
- Formula: `services/agents/recruitment/tools/matching.py::skill_overlap()`
- Embedding: `services/agents/recruitment/tools/embeddings.py::best_skill_similarity()`
- Descriptions: `services/agents/recruitment/tools/skill_descriptions.py` (40+ curated skills)
- API: `POST /jobs/{job_id}/matches` returns ranked candidates

## How Recruiter Copilot works

```
Recruiter Query: "Python engineers in SF with 5+ years, Talent Score 70+"
    ↓
    ├─→ Query Understanding Node
    │   - Extract: location=SF, skills=[Python], years_exp>=5, score>=70
    │
    ├─→ Hybrid Search Node
    │   - Hard skill filter: exact/fuzzy match Python
    │   - Semantic re-rank: embed query, find candidates in Qdrant space
    │   - Return top 20
    │
    ├─→ Reranking Node (LLM)
    │   - "Who fits best for this specific query?"
    │   - Returns top 5 with explanations
    │
    └─→ Explanation Node
        - "Found 5 candidates. Sarah has Python + 7yr exp + score 82,
          perfect fit for SF backend role."
```

**Key Code**:
- Copilot graph: `services/agents/recruitment/matching_graph.py::copilot_graph()`
- Nodes: query_understanding, hybrid_search, reranking, explanation
- API: `POST /copilot/query` (natural language → ranked candidates)

## Key design decisions

1. **Skill matching uses descriptions, not bare names**:
   - Bare embeddings: "Vue.js" and "React" both embed as ~0.65 similarity to "Photoshop"
   - With descriptions: "Vue.js" is 0.89 similar to "React", 0.66 from "Photoshop"
   - Measured & tuned; threshold = 0.80

2. **Matching is rules + embeddings, not pure LLM**:
   - Fast (1-3 sec for candidate pool scan)
   - Auditable (recruiter sees the formula)
   - No hallucination risk

3. **Copilot reranking uses LLM, matching doesn't**:
   - Matching formula is deterministic (speed + consistency)
   - Copilot adds LLM reranking for nuance (best fit explanations)
   - Separation of concerns

4. **Cold-start renormalization**:
   - Missing components (no Talent Score yet?) don't kill the score
   - Weights are renormalized to sum to 1.0
   - Never returns 0 or "inconclusive" as a fallback

## Limitations

- Candidate pool scans are O(n) — slow with 10k+ candidates
- Skill similarity threshold (0.80) is hardcoded (should be configurable)
- Copilot doesn't handle complex AND/OR logic ("Python AND React" vs "Python OR JavaScript")
- Location matching is exact string match, not geographic distance

## Where this lives

| Component | File |
|---|---|
| Matching formula | `services/agents/recruitment/tools/matching.py` |
| Skill embeddings | `services/agents/recruitment/tools/embeddings.py` |
| Skill descriptions | `services/agents/recruitment/tools/skill_descriptions.py` |
| Matching graph | `services/agents/recruitment/nodes/hybrid_search.py` |
| Copilot graph | `services/agents/recruitment/matching_graph.py` |
| API: Matching | `services/api/modules/recruitment/router.py:POST /jobs/{id}/matches` |
| API: Copilot | `services/api/modules/recruitment/router.py:POST /copilot/query` |
| Frontend: Matches | `apps/web/src/app/(recruiter)/jobs/[id]/matches/page.tsx` |
| Frontend: Copilot | `apps/web/src/app/(recruiter)/copilot/page.tsx` |
