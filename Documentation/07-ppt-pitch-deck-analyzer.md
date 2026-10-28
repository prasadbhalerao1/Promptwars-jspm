# AI PPT Analyzer & Presentation Intelligence

## What it does

Analyzes pitch decks uploaded by hackathon teams. Scores on problem clarity, solution innovativeness, business viability, and technical feasibility. Detects plagiarism and AI-generated content.

## How it works

```
Team uploads PowerPoint/PDF
    ↓
    ├─→ Extraction Phase
    │   ├─ If .ppt: Convert via LibreOffice → PDF
    │   └─ Extract slides: OCR text + image metadata
    │
    ├─→ Slide Embedding Phase
    │   - Embed each slide's text via sentence transformer
    │   - Store in Qdrant for plagiarism comparison
    │
    ├─→ Rubric Scoring Phase (LLM, temperature=0)
    │   ├─ Problem Clarity (0-100)
    │   │   "Is the problem statement clear and compelling?"
    │   │
    │   ├─ Solution Innovation (0-100)
    │   │   "How novel is the approach?"
    │   │   (Scored from the deck alone — see "Innovation is scored
    │   │    without the novelty signal" below)
    │   │
    │   ├─ Business Viability (0-100)
    │   │   "Is this a real business problem?"
    │   │
    │   └─ Technical Feasibility (0-100)
    │       "Can it actually be built in a weekend?"
    │
    ├─→ Plagiarism Check
    │   - Semantic similarity: slide embeddings vs prior submissions
    │   - One batched query_batch_points() call for the whole deck
    │   - Flag if cosine similarity >= DECK_PLAGIARISM_SIMILARITY_THRESHOLD (0.90)
    │   └─ On failure: raises, recorded as plagiarism_checked=false
    │      (NOT reported as "no matches" — see below)
    │
    ├─→ AI-Content Detection (heuristics)
    │   - Perplexity score: low perplexity = AI-generated
    │   - Lexical diversity: type/token ratio
    │   - Temporal consistency: dates align?
    │   └─ Signal (not auto-flagging; contributes to fraud score)
    │
    └─→ Composite Score
        - problem:0.25 + innovation:0.25 + business:0.25 + feasibility:0.25
        - Renormalized if any component missing
```

**Why background task?** Analysis is 15-40 seconds (extraction + LLM calls + embeddings). Used to block HTTP request with no progress feedback → frustrating UX. Now runs as `BackgroundTask`, returns immediately with status='processing'. Frontend polls `/presentations/{id}/status` until done.

## Key design decisions

1. **Background tasks, not blocking requests**:
   - Old: `POST /upload` waits 30 seconds, returns full report
   - New: `POST /upload` returns immediately, status='processing'
   - Frontend polls status, shows "Analyzing..." with spinner
   - Reason: User sees progress, can switch tabs, never thinks app hung

2. **Rubric scoring uses temperature=0**:
   - Reproducible scores (same pitch always gets same score)
   - No randomness = audit trail is meaningful
   - Tradeoff: less creative/nuanced responses (fine for rubric)

3. **Plagiarism corpus starts empty**:
   - Cold-start: first 10 pitches won't match anything (correct, no prior decks)
   - After 50+ submissions: corpus becomes useful
   - Acknowledged limitation, not a bug

4. **A failed plagiarism check is not a pass**:
   - `find_and_record_matches()` raises `PlagiarismCheckUnavailable` rather than returning
     an empty list, and the node records `plagiarism_checked=false` on the score row.
   - Why this needed fixing: an empty match list renders to the reader as *"No similarity
     matches found against prior submissions"* — an affirmative all-clear. The old
     `except Exception: return []` made "checked, clean" and "check exploded" the same
     value. That is not hypothetical: a Qdrant client method removed in 1.18 raised
     `AttributeError` inside that swallow, and **every deck was reported clean**.
   - The analysis still completes when the check fails — the four rubric scores are
     independent and worth showing — but the UI says the deck could not be compared
     instead of claiming it passed.

5. **Innovation is scored without the novelty signal**:
   - The innovation scorer used to read `state["plagiarism_matches"]` to build a "N slides
     matched prior submissions" hint for the LLM, with a comment noting the data "may not
     have landed in this superstep yet".
   - It never had. `similarity_plagiarism` sits a full superstep further down a parallel
     branch (`content_extraction → slide_embedding → similarity_plagiarism`), while the
     innovation node runs immediately after `content_extraction`. The hint was always
     `None`.
   - Worse than dead code: had the scheduling ever changed, the same deck would score
     differently run to run — nondeterminism in a number persisted against a real
     submission. The read is gone; plagiarism matches are surfaced to the reader directly
     rather than silently discounted inside a score they cannot inspect.

6. **AI-content is heuristic, not auto-flagging**:
   - Signal recorded (via verification_records), never auto-rejects
   - Human reviewer judges whether high perplexity score = suspicious or just formal writing
   - Similar to fraud engine: evidence → human review

## Limitations

- LibreOffice dependency for legacy .ppt (not all .ppt types fully supported)
- Rubric weights are equal (0.25 each) and not yet per-hackathon configurable; the
  similarity threshold and LLM token/timeout budgets *are* now env-tunable
- Plagiarism corpus is within-platform only (not checked against internet)
- AI-content detection is statistical, not forensic (imperfect)

## Where this lives

| Component | File |
|---|---|
| Extraction | `services/agents/ppt_analyzer/tools/extraction.py` |
| Rubric scoring | `services/agents/ppt_analyzer/tools/rubric_scoring.py` |
| Plagiarism detection | `services/agents/ppt_analyzer/tools/plagiarism.py` |
| AI-content heuristic | `services/agents/ppt_analyzer/tools/ai_content_heuristic.py` |
| Embedding model | `services/agents/ppt_analyzer/tools/embeddings.py` |
| PPT analyzer graph | `services/agents/ppt_analyzer/graph.py` |
| API: Upload + analyze | `services/api/modules/presentations/router.py:POST /presentations/analyze` |
| API: Get status | `services/api/modules/presentations/router.py:GET /presentations/{id}/status` |
| Frontend: Upload | `apps/web/src/app/(candidate)/pitch-deck/page.tsx` |
| Frontend: Results | `apps/web/src/app/pitch-deck/[id]/page.tsx` |
| DB: Presentation model | `packages/db/models/presentation.py::Presentation` |
| DB: Score model | `packages/db/models/presentation.py::PresentationScore` |
| Migration: `plagiarism_checked` | `packages/db/migrations/versions/c7e2a4f81b30_plagiarism_checked.py` |
| Tests: graph ordering | `services/api/tests/test_ppt_graph_ordering.py` |
| Tests: plagiarism disclosure | `services/api/tests/test_plagiarism_failure_disclosure.py` |
