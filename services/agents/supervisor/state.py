"""Supervisor graph state — doc/multi-agent-architecture/07 §2.

Minimal demo scope: two dispatch targets (Module 01 Candidate Intelligence, Module 02
Recruitment), not full coverage of all 6 modules — Modules 05/06 are out of scope for
this pass (05 is only a cross-module *event source*, handled separately by
`services/api/core/event_consumer.py`, not by this graph; 06 belongs to a different
concurrent session entirely) and Modules 03/04 dispatch targets are straightforward
follow-up work once this pattern is proven, per the assignment brief's "keep this
genuinely minimal — it's a demo of the supervisor pattern working end-to-end" note.
"""

from typing import Any, Optional, TypedDict


class SupervisorState(TypedDict, total=False):
    raw_request: str
    candidate_id: Optional[str]
    job_id: Optional[str]
    intent: Optional[str]  # "candidate_score" | "job_match" — set by classify_intent
    result: Optional[dict[str, Any]]
    error: Optional[str]
