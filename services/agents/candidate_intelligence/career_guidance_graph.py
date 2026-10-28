"""FR-4 (AI Career Guidance System) — a separate on-demand subgraph, not part of Flow
A's ingestion fan-out (`graph.py`).

    skill_gap_analysis --+--> certification_mapping --\
                          +--> career_roadmap ----------+--> END
                          +--> salary_prediction -------/

Doc 01 §3's own mermaid flowchart shows "Generate Career Guidance" (G) fanning out from
"Merge into One Profile" (E) in parallel with "Compute Talent Score" (F) — but doc 01
§8 also requires the salary regression to take "talent score" as a feature, which is a
real ordering dependency the diagram doesn't show. Rather than silently ignore one of
the two docs, this subgraph is triggered on-demand from `GET /candidates/me/
career-guidance` (matching that same doc's §9 endpoint) using whatever Talent Score is
already persisted at request time — so it always runs after scoring exists (or
degrades gracefully if it doesn't yet, see `nodes/salary_prediction.py`), instead of
racing it in the same superstep. See `.agents/decisions.md` for the full reasoning.

`skill_gap_analysis` must run first since `certification_mapping`/`career_roadmap`/
`salary_prediction` all consume its `resolved_target_role`/`skill_gaps` output; those
three then run in the same superstep — each returns only its own new keys (no overlap),
so no `Annotated`/reducer channels are needed (see `state.py`'s `CareerGuidanceState`).
"""

from langgraph.graph import END, START, StateGraph

from services.agents.candidate_intelligence.nodes import (
    career_roadmap,
    certification_mapping,
    salary_prediction,
    skill_gap_analysis,
)
from services.agents.candidate_intelligence.state import CareerGuidanceState


def build_career_guidance_graph():
    graph = StateGraph(CareerGuidanceState)

    graph.add_node("skill_gap_analysis", skill_gap_analysis.run)
    graph.add_node("certification_mapping", certification_mapping.run)
    graph.add_node("career_roadmap", career_roadmap.run)
    graph.add_node("salary_prediction", salary_prediction.run)

    graph.add_edge(START, "skill_gap_analysis")
    graph.add_edge("skill_gap_analysis", "certification_mapping")
    graph.add_edge("skill_gap_analysis", "career_roadmap")
    graph.add_edge("skill_gap_analysis", "salary_prediction")
    graph.add_edge("certification_mapping", END)
    graph.add_edge("career_roadmap", END)
    graph.add_edge("salary_prediction", END)

    return graph.compile()


_compiled_career_guidance_graph = None


def get_career_guidance_graph():
    global _compiled_career_guidance_graph
    if _compiled_career_guidance_graph is None:
        _compiled_career_guidance_graph = build_career_guidance_graph()
    return _compiled_career_guidance_graph
