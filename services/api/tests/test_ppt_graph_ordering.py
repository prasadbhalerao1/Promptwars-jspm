"""The innovation score must not depend on a sibling branch's timing.

`innovation_business_impact` read `state["plagiarism_matches"]` to build a "novelty
context" string that it fed to the LLM. That key is written by `similarity_plagiarism`,
which is not a predecessor of this node — it sits one superstep further down a parallel
branch (`content_extraction -> slide_embedding -> similarity_plagiarism`).

The in-code comment described this as "may not have landed in this superstep yet", which
understates it: with the graph as drawn, it has *never* landed. `innovation_business_impact`
runs in the superstep right after `content_extraction`; `similarity_plagiarism` runs one
after that. So the novelty context was dead code that silently evaluated to None on every
run, and the score shown to organizers was computed without the novelty signal the design
called for.

Either shape is defensible, but they must not be confused: reading a value that is
sometimes present makes the persisted score nondeterministic across runs, which for a
score attached to a real submission is the worst of the options.
"""

from __future__ import annotations

import inspect


def _predecessors(edges: list[tuple[str, str]], node: str) -> set[str]:
    """Every node that must complete before `node` starts."""
    seen: set[str] = set()
    frontier = [src for src, dst in edges if dst == node]
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(src for src, dst in edges if dst == current)
    return seen


def _graph_edges() -> list[tuple[str, str]]:
    from services.agents.ppt_analyzer.graph import build_graph

    compiled = build_graph()
    edges: list[tuple[str, str]] = []
    for edge in compiled.get_graph().edges:
        edges.append((edge.source, edge.target))
    return edges


def test_similarity_plagiarism_is_not_a_predecessor_of_innovation() -> None:
    """Pins the structural fact the fix rests on."""
    edges = _graph_edges()
    preds = _predecessors(edges, "innovation_business_impact")
    assert "content_extraction" in preds
    assert "similarity_plagiarism" not in preds, (
        "if this becomes a real dependency, the node may read plagiarism_matches again"
    )


def test_innovation_node_does_not_read_a_non_predecessor_key() -> None:
    """The node must not depend on state a sibling branch has not written yet.

    Reading it is what made the score's inputs a function of scheduling rather than of
    the deck.
    """
    from services.agents.ppt_analyzer.nodes import innovation_business_impact

    source = inspect.getsource(innovation_business_impact)
    code = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "plagiarism_matches" not in code, (
        "innovation_business_impact reads a key written by a parallel sibling branch"
    )


def test_aggregation_still_joins_every_scoring_branch() -> None:
    """The fix must not be to sever an edge — aggregation still needs all five."""
    edges = _graph_edges()
    preds = _predecessors(edges, "aggregation")
    for branch in (
        "problem_solution_clarity",
        "innovation_business_impact",
        "technical_feasibility",
        "similarity_plagiarism",
        "ai_content_heuristic",
    ):
        assert branch in preds, f"aggregation lost its dependency on {branch}"
