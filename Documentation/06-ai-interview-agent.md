# AI Interview Agent

## What it does

Conducts multi-turn technical interviews with candidates. Agent asks questions, evaluates answers in real-time, decides whether to go deeper, move to next topic, or end. Produces a structured report with technical/communication ratings.

## How it works (the conditional graph)

```
Start Interview Session
    ↓
    └─→ Topic Plan (from job description)
           - "Technical Depth"
           - "System Design"  
           - "Communication"
    ↓
    └─→ For each topic:
           ├─→ Generate Question (context: candidate level, topic)
           │
           ├─→ Candidate Responds
           │
           ├─→ Turn Evaluation Node (LLM)
           │   - Score this answer: 0-100
           │   - Assess: clarity, depth, correctness
           │   - Update running total for topic
           │
           └─→ Routing Decision (conditional edge):
                   ├─ follow_up_count < 3? → Ask follow-up
                   ├─ Running score < threshold? → Escalate difficulty
                   ├─ All topics done? → End
                   └─ Else → Next topic
    ↓
    └─→ Final Report Generation
           - Technical Rating: avg(topic_scores)
           - Communication Rating: hedging language, clarity metrics
           - Confidence Signal: per-topic confidence
           - Hiring Recommendation: "Strong hire", "Hire", "Maybe", "No hire"
```

**Key Code**:
- Graph: `services/agents/assessment/interview_graph.py`
- Turn evaluation: `services/agents/assessment/nodes/turn_evaluation.py`
- Topic plan: built by the router (`_default_topic_plan`, or derived from an interview
  template's questions), not a graph node — the graph receives it in state. Capped at
  `INTERVIEW_MAX_TOPICS`, since worst-case interview length is `2 x len(topic_plan)` turns
- Report generation: `services/agents/assessment/nodes/interview_report.py`
- API: `POST /interviews/sessions/{id}/turn` (candidate answers → LLM evaluates → next question)

## Why turn-based (not one giant LLM call)?

```
Option A: One LLM call per interview
    ├─ Pro: Simple, single prompt
    └─ Con: 1-hour conversation as one prompt
           - Token limit exceeded
           - No adaptive depth
           - No real-time feedback

Option B: Turn-based routing (chosen)
    ├─ Per-turn LLM call
    ├─ Conditional edges based on live scores
    ├─ Follow-up questions tailored to answer quality
    ├─ Pro: Scalable, adaptive, realtime feedback
    └─ Con: More complex orchestration
```

## Key design decisions

1. **Interview is turn-based with running state**:
   - `interview_sessions.state` (JSONB) tracks: topic_plan, current_topic_idx, per_topic_scores, follow_up_count
   - Each turn updates state, persists to DB
   - No LangGraph checkpointer; manual state management

2. **Evaluation is LLM-based, not rules**:
   - An LLM can understand nuance in technical explanations
   - Rules ("keyword count > 5 = pass") fail on paraphrased answers
   - Tradeoff: LLM is slow + expensive; run selectively

3. **Follow-up limit per topic (max 3)**:
   - Prevents endless drilling into one topic
   - Keeps interview to reasonable length
   - If score is low after 3 follow-ups, move on

4. **Communication rating from transcript analysis**:
   - Hedging language: "I think...", "maybe..."
   - Response structure: clear problem statement → solution → tradeoffs
   - Never voice/emotion analysis (privacy)

## Limitations

- Interview evaluation is subjective; two candidates answering identically might get different scores from different LLM runs (temperature, model version)
- Follow-up routing is simple (depth/topic-switching); doesn't handle candidate anxiety or pace changes
- Report doesn't explain WHY score is what it is (just the number)
- No recorded video storage (candidate's device only); no transcription

## Where this lives

| Component | File |
|---|---|
| Interview graph | `services/agents/assessment/interview_graph.py` |
| Turn evaluation | `services/agents/assessment/nodes/turn_evaluation.py` |
| Topic plan construction | `services/api/modules/assessments/router.py::_default_topic_plan` |
| Report generation | `services/agents/assessment/nodes/interview_report.py` |
| API: Submit turn | `services/api/modules/assessments/router.py:POST /interviews/{id}/turn` |
| API: Get report | `services/api/modules/assessments/router.py:GET /interviews/{id}/report` |
| Frontend: Interview UI | `apps/web/src/app/(candidate)/interview/[sessionId]/page.tsx` |
| DB: Session state | `packages/db/models/assessment.py::InterviewSession.state` |
| DB: Report | `packages/db/models/assessment.py::InterviewReport` |
| DB: Transcript | `packages/db/models/assessment.py::InterviewTranscriptTurn` |
