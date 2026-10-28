# Skill Verification & Assessments

## What it does

**Coding Assessments**: Candidates solve real coding challenges (LeetCode-style). System grades via unit tests + LLM code review.

**MCQ Assessments**: Multiple-choice knowledge tests. Auto-graded with instant feedback.

**Project Analysis**: Candidates submit portfolio projects. System analyzes code quality (AST metrics + LLM review).

**Team Contribution Analytics**: For hackathon teams, determines who actually did what via git commit analysis.

## How Coding Assessments work

```
Candidate receives coding problem (signature + tests provided)
    ↓
    ├─→ Candidate submits solution code
    │
    ├─→ Auto-Grade Phase
    │   ├─ Run unit tests: PASS/FAIL
    │   └─ Static Analysis: complexity (cyclomatic, nested depth), style (via radon/lizard)
    │
    ├─→ LLM Review Phase (if time permits, optional)
    │   - "Is this code production-ready? What's the trade-off?"
    │   - Judgment-tier LLM (higher quality, slower)
    │
    └─→ Score: (test_pass_weight=0.40 + static_analysis_weight=0.35 + llm_review_weight=0.25)
           - Renormalized if LLM review unavailable
```

**Key Code**:
- Submission: `POST /assessments/{id}/submit` in router
- Grading: `services/agents/assessment/tools/static_analysis.py` (radon, lizard)
- LLM review: `services/agents/assessment/nodes/llm_code_review.py` (judgment-tier)
- Storage: `Submission` model (code_or_answers, static_analysis, llm_review, score)

## How Project Analysis works

```
Candidate submits GitHub repo link
    ↓
    ├─→ Clone repo locally
    │
    ├─→ Static Analysis (no LLM)
    │   ├─ Line count, file count
    │   ├─ Language distribution
    │   ├─ Cyclomatic complexity (radon)
    │   ├─ Maintainability index
    │   └─ Test coverage (if tests exist)
    │
    ├─→ AST-based Clone Detection
    │   - "Did this match a known solution?" (copydetect)
    │   - Catches variable renames, structural plagiarism
    │
    └─→ LLM Architecture Review (judgment-tier)
        - "Design patterns used?"
        - "Scalability concerns?"
        - "Production-ready?"
```

**Key Code**:
- Static analysis: `services/agents/assessment/tools/static_analysis.py`
- Plagiarism: `services/agents/fraud/tools/structural_similarity.py` (copydetect)
- LLM review: `services/agents/assessment/nodes/llm_code_review.py`

## How Team Contribution Analytics works

```
Hackathon team submits GitHub repo
    ↓
    ├─→ Commit Attribution
    │   - Parse commit history: who committed what, when
    │   - Match git author → platform candidate via GitHub username
    │   - Handle squashed/rebased commits
    │
    ├─→ Contribution Weighting
    │   - Lines added/deleted per person
    │   - Commit frequency (avoiding "100 one-line commits" gaming)
    │   - Recency bias (work done late in hackathon counts more)
    │
    └─→ Contribution Report
        - Per-member breakdown: 30% Alice, 40% Bob, 30% Charlie
        - Methodology disclosed (git-based, not biometric/sentiment)
        - CSV export for organizers
```

**Key Code**:
- Commit parsing: `services/agents/assessment/nodes/commit_attribution.py`
- Weighting: `services/agents/assessment/tools/contribution_weighting.py`
- Report generation: `services/agents/assessment/nodes/contribution_report.py`

## Key design decisions

1. **Combine mechanical static analysis with LLM judgment**:
   - Static only: misses algorithmic inefficiency, doesn't explain why
   - LLM only: slow, expensive, potentially hallucinating
   - Both: fast baseline + nuanced feedback

2. **Plagiarism uses AST-level clone detection, not embeddings**:
   - Detects "same logic, renamed variables" (harder to game than text diff)
   - Token-structure fingerprinting (copydetect) is well-studied
   - Embeddings would catch "semantically similar" (false positives)

3. **Contribution attribution via git commits, not biometrics**:
   - Auditable: anyone can verify by reading commit history
   - Fair: code is code, regardless of contributor's typing speed
   - Legal: no facial recognition, no keystroke analysis

4. **Test presence is rewarded, not required**:
   - Code WITH tests gets bonus (maintainability signal)
   - Code WITHOUT tests still grades on static analysis + LLM
   - Never penalizes absence of tests

## Limitations

- Static analysis is language-specific; only works for languages radon/lizard support
- LLM code review is expensive (used selectively, not on every submission)
- Commit attribution breaks with squashed merges (rebased history unclear)
- Plagiarism detection only checks within-platform corpus (not against GitHub)

## Where this lives

| Component | File |
|---|---|
| Coding assessment submission | `services/api/modules/assessments/router.py` |
| Static analysis (radon, lizard) | `services/agents/assessment/tools/static_analysis.py` |
| LLM code review | `services/agents/assessment/nodes/llm_code_review.py` |
| Plagiarism (copydetect) | `services/agents/fraud/tools/structural_similarity.py` |
| Commit attribution | `services/agents/assessment/nodes/commit_attribution.py` |
| Contribution weighting | `services/agents/assessment/tools/contribution_weighting.py` |
| Contribution report | `services/agents/assessment/nodes/contribution_report.py` |
| Frontend: Assessments | `apps/web/src/app/(candidate)/assessments/page.tsx` |
| DB: Submission model | `packages/db/models/assessment.py::Submission` |
| DB: Contribution report | `packages/db/models/assessment.py::ContributionReport` |
