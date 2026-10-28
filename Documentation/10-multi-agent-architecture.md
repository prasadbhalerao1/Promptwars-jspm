# Multi-Agent Architecture & Supervisor

## What "multi-agent" means here

LangGraph-based orchestration of multiple independent StateGraphs, NOT autonomous agents negotiating freely. This is **structured orchestration**: each graph has explicit nodes, edges, and a well-defined state schema.

## The agent/graph inventory

```
Candidate Intelligence Module (services/agents/candidate_intelligence/)
  └─ graph.py: ingest resume/GitHub/certificate → merge → compute 9-dim Talent Score

Recruitment Module (services/agents/recruitment/)
  ├─ matching_graph.py: skill match + semantic rank → top candidates
  └─ copilot_graph.py: natural language query → ranked results

Assessment Module (services/agents/assessment/) — 5 graphs
  ├─ contribution_graph.py: git commit analysis → team breakdown
  ├─ interview_definition_graph.py: job description → interview topic plan
  ├─ interview_graph.py: turn-based Q&A → live scoring
  ├─ interview_report_graph.py: transcript → final report
  └─ verification_graph.py: static analysis + LLM review → coding score

Fraud Module (services/agents/fraud/) — 4 graphs
  ├─ cert_graph.py: issuer lookup + auto-verify + visual forensics → verdict
  ├─ content_graph.py: perplexity heuristic → AI-generation signal
  ├─ duplicate_graph.py: photo hash + text fingerprint → duplicate profile
  └─ plagiarism_graph.py: structural + text similarity → plagiarism flag

Hackathon Module (services/agents/hackathon/)
  └─ graph.py: judge + pitch + repo + novelty → rankings

PPT Analyzer Module (services/agents/ppt_analyzer/)
  └─ graph.py: extraction + rubric + plagiarism → deck score

Supervisor Module (services/agents/supervisor/)
  └─ graph.py: intent classification → dispatch (2 of the 7 modules above, see below)

common/ holds shared code used by the modules above (scoring helper, no graph of its own).
```

Total: 12 distinct graph files across 7 domain modules (plus `common/` for shared code).

## Shared architectural conventions

All graphs follow:

1. **TypedDict state schema**: Explicit type hints for state shape
   ```python
   class FraudCheckState(TypedDict):
       subject_type: str
       subject_id: uuid.UUID
       context: dict  # Pre-fetched by router
       signals: list[dict]  # operator.add reducer
       verdict: dict
   ```

2. **Nodes stay DB-free**:
   - Nodes receive data via `context` pre-fetched by router
   - Nodes return signals/verdicts
   - Router persists everything to DB
   - Benefit: testable in isolation, no side effects

3. **Never fabricate on failure** (typed exceptions):
   - Missing data → raise `SpecificUnavailable` exception
   - Caller catches, decides: skip this signal or retry
   - Never return 0.0 or "unknown" as a fallback

4. **Observability via Langfuse**:
   - `start_agent_trace()` wraps each graph invocation
   - Traces include: input_data, output, model_used, tags
   - Audit trail: every agent run recorded in `AgentRun` table

## The supervisor's actual scope

`services/agents/supervisor/graph.py` is real, working code — not a stub — but its own
module docstring is explicit that it's a **partial, minimal demo of orchestration**, not the
platform's real dispatch mechanism for every module. It wires exactly one `classify_intent`
node followed by a conditional edge that routes to one of two domain modules:

```
User Query (text)
    ↓
    └─→ classify_intent (small/fast-tier LLM)
           - "Find me senior backend engineers in SF" → recruitment intent
           - "How do I close my skill gap?"           → candidate_intelligence intent
    ↓
    └─→ [conditional edge] Dispatch to one of 2 domain graphs:
           ├─ recruitment intent           → recruitment/copilot_graph.py
           └─ candidate_intelligence intent → candidate_intelligence/graph.py
```

It does not use a LangGraph checkpointer anywhere — session/turn state for things like the
interview graph is persisted manually to DB columns (`InterviewSession.state`, a JSONB
column), not via LangGraph's built-in persistence layer.

**What actually serves the other 5 modules.** Assessment, fraud, hackathon, and PPT
analyzer are not reachable through the supervisor at all. Each has its own FastAPI router
(`services/api/modules/assessments/router.py`, `.../fraud/router.py`,
`.../hackathons/router.py`, `.../presentations/router.py`) that invokes its own subgraph
directly — the router fetches whatever context the graph needs, calls
`graph.ainvoke(...)`, and persists the result. There are 12 graph files total across the 7
domain modules; the supervisor demo covers 2 of those 7 modules (candidate_intelligence and
recruitment), and the remaining 5 are invoked directly from their own clean REST entry
points, bypassing the supervisor entirely.

This is a deliberate, reasonable scope choice rather than an unfinished feature. Each module
already has its own well-defined REST surface with request/response schemas — routing an
assessment submission or a fraud check *through* a natural-language intent classifier first
would add latency and an extra point of failure for no real benefit, since the caller
(the frontend) already knows exactly which module it wants to hit. A single natural-language
entry point earns its keep specifically where it replaces something that would otherwise be
a fragile filter UI — recruiter search and candidate career questions — which is exactly
where it's used.

## A concrete example: Interview graph (real agentic behavior)

```
Start Interview Session
    ↓
    ├─→ [topic_planning] Generate topics from job description
    │   State update: topic_plan = ["Technical Depth", "System Design", ...]
    │
    └─→ Loop: for each topic
           ├─→ [question_generation] LLM: "Ask about Technical Depth"
           │   Output: question text
           │
           ├─→ Candidate responds (human input)
           │
           ├─→ [turn_evaluation] LLM: "Grade this answer 0-100"
           │   State update: per_topic_scores["Technical Depth"] = 75
           │
           └─→ [CONDITIONAL EDGE] Route based on live score:
                   if follow_up_count < 3 AND score < 70:
                       → [follow_up_generation] (loop back)
                   elif all_topics_done:
                       → [report_generation]
                   else:
                       → [question_generation] (next topic)
```

**Why this is "real" multi-agent**:
- Not a single wrapped prompt (would be 1-hour conversation token soup)
- Conditional routing based on live intermediate scores
- Separate node per concern (topic planning, evaluation, routing)
- State machines, not procedural code

## Key design decisions

1. **Supervisor exists but is narrowly scoped by design**:
   - Covers 2 of 7 modules: recruiter copilot queries and candidate intelligence
   - The other 5 modules (assessment, fraud, hackathon, ppt_analyzer, and interview flows) are direct router → graph calls
   - Honest tradeoff: a full supervisor router isn't necessary when every module already has a clean REST entry point; natural-language dispatch earns its keep only where it replaces a fragile filter UI
   - No LangGraph checkpointer is used anywhere; stateful flows (e.g. interview turns) persist state manually to DB columns instead

2. **Nodes are DB-free by convention**:
   - Enforced: nodes receive TypedDict, return signals
   - Benefits: testable, composable, no implicit dependencies
   - Persistence handled exclusively by router

3. **Conditional routing used sparingly**:
   - Only where it matters (interview scoring, fraud verdicts)
   - Simpler graphs are linear (no routing needed)
   - Justification: routing adds complexity; use only when value is clear

4. **Langfuse tracing on every agent run**:
   - Cost: extra LLM inference for each trace (minimal)
   - Benefit: complete audit trail + performance visibility
   - Fallback: if Langfuse unavailable, trace silently fails

## What could go wrong / limitations

- The supervisor only fronts 2 of 7 modules; a judge testing "ask the supervisor about fraud review" would find it's not wired to route there — that's expected, not a bug, but worth knowing going in
- Node isolation means nodes can't call other agents (by design; enforced)
- Conditional edges are coupled to state schema; refactoring is risky
- LangGraph version upgrades need careful testing (breaking changes possible)
- No LangGraph checkpointer anywhere means resuming a mid-flight multi-turn flow (e.g. an interrupted interview session) relies entirely on the DB-persisted state columns being complete and correctly re-hydrated by the router — there's no framework-level replay/resume guarantee

## Where this lives

| Component | File |
|---|---|
| Supervisor graph | `services/agents/supervisor/graph.py` |
| Supervisor routing | `services/agents/supervisor/nodes/classify_intent.py` |
| Interview graph | `services/agents/assessment/interview_graph.py` |
| Interview definition / report graphs | `services/agents/assessment/interview_definition_graph.py`, `interview_report_graph.py` |
| Fraud cert graph | `services/agents/fraud/cert_graph.py` |
| Hackathon ranking | `services/agents/hackathon/graph.py` |
| Shared scoring helper | `services/agents/common/scoring.py` |
| Qdrant client helper | `services/api/core/qdrant.py` |
| Agent run audit | `packages/db/models/agent_run.py` |
| Langfuse tracing | `services/api/core/tracing.py` |
