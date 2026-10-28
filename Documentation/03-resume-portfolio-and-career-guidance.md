# AI Resume & Portfolio Builder + AI Career Guidance System

## What these features do (plain English)

**Resume Builder**: Generates ATS-optimized resumes and cover letters tailored to specific jobs, with LLM generation backed by a fact-checking guardrail that ensures claims match verified profile data.

**Portfolio Publisher**: Transforms resume/GitHub data into a public portfolio page (shareable URL like `platform.com/jane-doe`).

**Career Guidance**: Analyzes skill gaps against desired roles using Qdrant, predicts salary using a pre-trained ML model, and recommends learning paths.

## How Resume Generation works

```
Candidate Profile + Target Job
    ↓
    ├─→ LLM: Draft optimized resume/cover letter
    │
    └─→ Fact-Check Guardrail
           - Education dates match?
           - GitHub projects exist?
           - Skills in verified profile?
           ├─ PASS → Return document
           └─ FAIL → Reject, explain why
```

**Key Code**: 
- Trigger: `POST /candidates/me/resume/generate` 
- Logic: `services/agents/candidate_intelligence/tools/resume.py`
- Guardrail: `FactCheckFailed` exception on mismatch
- Storage: `CandidateProfile.generated_documents` (JSONB)

## How Portfolio Publishing works

```
Generated Resume + GitHub Data
    ↓
    └─→ Public Portfolio Page
           - Name, headline, location
           - Talent Score, GitHub stats
           - Top 5 projects + tech stack
           - Verified skills + education
           - Experience timeline
    ↓
    └─→ Public URL: platform.com/{username}
           - Shareable, no auth required
           - Candidate controls visibility
```

## How Career Guidance works

### Skill Gap Analysis

```
Candidate Skills → Embed in Qdrant
Target Role → Embed in Qdrant
    ↓
    └─→ Cosine Similarity
           - Identify gaps (role needs X, candidate lacks Y)
           - Rank by market demand
           - Suggest learning resources
```

**Algorithm**: Embed candidate skills via sentence transformer, query Qdrant for role requirements, compute gaps.

### Salary Prediction

```
Candidate Profile (skills, experience, location, etc.)
    ↓
    └─→ Offline-Trained ML Model
           - Trained ONCE on historical data
           - Returns: $low, $high, $percentile
           
Why offline? Fast, consistent, auditable. Avoids per-request retraining.
```

**Key Code**: `services/agents/candidate_intelligence/tools/train_salary_model.py`

### Learning Recommendations

```
Skill Gaps + Constraints (time, budget, format)
    ↓
    └─→ LLM: Generate ranked paths
           - "Close ML gap in 3 months: X, Y, Z"
           - Links to courses, estimated time/cost
```

## Key design decisions

1. **Fact-check guardrail on resume (deterministic, not LLM judge)**:
   - LLMs hallucinate; deterministic check is trustworthy
   - Fail-safe: reject generation, don't silently fabricate

2. **Salary model is offline-trained**:
   - Real-time LLM calls per request are slow
   - ML model is fast, consistent, auditable
   - Tradeoff: requires retraining as market shifts

3. **Portfolio is public but unpublishable**:
   - Candidate controls visibility
   - Shareable URL for recruiters
   - No auth required

4. **Skill gaps use embeddings, not keyword matching**:
   - "Python" vs "Python3" vs "Py" all match same concept
   - Semantic similarity catches related skills

## Limitations

- Resume guardrail is strict (missed skills won't pass)
- Salary model reflects training data, not real-time market
- Skill gap taxonomy covers ~20 common roles only
- Learning recommendations may be outdated or expensive

## Where this lives

| Component | File |
|---|---|
| Resume generation | `services/agents/candidate_intelligence/tools/resume.py` |
| Skill gap analysis | `services/agents/candidate_intelligence/tools/skill_gap.py` |
| Salary model | `services/agents/candidate_intelligence/tools/train_salary_model.py` |
| Role taxonomy | `services/agents/candidate_intelligence/tools/role_taxonomy.py` |
| API endpoints | `services/api/modules/candidates/router.py` |
| Frontend: Resume builder | `apps/web/src/app/(candidate)/resume-builder/page.tsx` |
| Frontend: Career | `apps/web/src/app/(candidate)/career/page.tsx` |
| Frontend: Public portfolio | `apps/web/src/app/(public)/[username]/page.tsx` |
