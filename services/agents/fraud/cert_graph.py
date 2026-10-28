"""Certificate Verification subgraph — doc 06 §4:

    issuer_lookup --[verification URL found]--> auto_verify --> cert_verdict --> END
    issuer_lookup --[no API/URL]--------------> visual_forensics --> cert_verdict --> END

Invoked from `POST /verification/certificates/{id}/check`. Router pre-fetches the
certificate's `issuer`/`title`/`credential_id`/`ocr_confidence` (Module 01's
`certifications` table, read-only) plus the certificate file's `public_url` if one exists
(Module 01's `files` table) into `state["context"]` before calling `ainvoke()`.
"""

from langgraph.graph import END, START, StateGraph

from services.agents.fraud.nodes import auto_verify, cert_verdict, issuer_lookup, visual_forensics
from services.agents.fraud.state import FraudCheckState


def _route_after_issuer_lookup(state: FraudCheckState) -> str:
    return "auto_verify" if state["context"]["issuer_lookup_result"]["resolvable"] else "visual_forensics"


def build_cert_graph():
    graph = StateGraph(FraudCheckState)

    graph.add_node("issuer_lookup", issuer_lookup.run)
    graph.add_node("auto_verify", auto_verify.run)
    graph.add_node("visual_forensics", visual_forensics.run)
    graph.add_node("cert_verdict", cert_verdict.run)

    graph.add_edge(START, "issuer_lookup")
    graph.add_conditional_edges(
        "issuer_lookup", _route_after_issuer_lookup, {"auto_verify": "auto_verify", "visual_forensics": "visual_forensics"}
    )
    graph.add_edge("auto_verify", "cert_verdict")
    graph.add_edge("visual_forensics", "cert_verdict")
    graph.add_edge("cert_verdict", END)

    return graph.compile()


_compiled_cert_graph = None


def get_cert_graph():
    global _compiled_cert_graph
    if _compiled_cert_graph is None:
        _compiled_cert_graph = build_cert_graph()
    return _compiled_cert_graph
