"""PPT Analyzer subgraph — doc 04 §4 mermaid flowchart:

    format_normalization -> content_extraction
    content_extraction -> slide_image_ocr, slide_embedding, problem_solution_clarity,
                           innovation_business_impact, ai_content_heuristic
    slide_embedding -> similarity_plagiarism
    content_extraction & slide_image_ocr -> technical_feasibility  (join)
    problem_solution_clarity & innovation_business_impact & technical_feasibility &
        similarity_plagiarism & ai_content_heuristic -> aggregation  (join)
    aggregation -> summary_suggestions -> END

Invoked synchronously from the upload route for now (same as candidate_intelligence's
Flow A) — doc 04 §9 calls for an `arq` background worker, but no `arq` worker
infrastructure exists yet anywhere in this repo (checked services/, no worker
entrypoint), so building one exclusively for this module was out of scope for this
pass. `arq` IS already an installed dependency; see .agents/decisions.md for the
call to revisit this once a shared worker entrypoint exists.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.ppt_analyzer.nodes import (
    ai_content_heuristic,
    aggregation,
    content_extraction,
    format_normalization,
    innovation_business_impact,
    problem_solution_clarity,
    similarity_plagiarism,
    slide_embedding,
    slide_image_ocr,
    summary_suggestions,
    technical_feasibility,
)
from services.agents.ppt_analyzer.state import PitchAnalysisState


def build_graph():
    graph = StateGraph(PitchAnalysisState)

    graph.add_node("format_normalization", format_normalization.run)
    graph.add_node("content_extraction", content_extraction.run)
    graph.add_node("slide_image_ocr", slide_image_ocr.run)
    graph.add_node("slide_embedding", slide_embedding.run)
    graph.add_node("similarity_plagiarism", similarity_plagiarism.run)
    graph.add_node("problem_solution_clarity", problem_solution_clarity.run)
    graph.add_node("innovation_business_impact", innovation_business_impact.run)
    graph.add_node("technical_feasibility", technical_feasibility.run)
    graph.add_node("ai_content_heuristic", ai_content_heuristic.run)
    graph.add_node("aggregation", aggregation.run)
    graph.add_node("summary_suggestions", summary_suggestions.run)

    graph.add_edge(START, "format_normalization")
    graph.add_edge("format_normalization", "content_extraction")

    graph.add_edge("content_extraction", "slide_image_ocr")
    graph.add_edge("content_extraction", "slide_embedding")
    graph.add_edge("content_extraction", "problem_solution_clarity")
    graph.add_edge("content_extraction", "innovation_business_impact")
    graph.add_edge("content_extraction", "ai_content_heuristic")

    graph.add_edge("slide_embedding", "similarity_plagiarism")

    # Join: technical_feasibility needs both extraction and OCR/diagram-understanding output.
    graph.add_edge("content_extraction", "technical_feasibility")
    graph.add_edge("slide_image_ocr", "technical_feasibility")

    # Join: aggregation needs all 4 scoring/signal branches.
    graph.add_edge("problem_solution_clarity", "aggregation")
    graph.add_edge("innovation_business_impact", "aggregation")
    graph.add_edge("technical_feasibility", "aggregation")
    graph.add_edge("similarity_plagiarism", "aggregation")
    graph.add_edge("ai_content_heuristic", "aggregation")

    graph.add_edge("aggregation", "summary_suggestions")
    graph.add_edge("summary_suggestions", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
