"""The TypeScript client's types must not fall behind the API's responses.

There is no codegen step between FastAPI and `apps/web/src/lib/api.ts` — the interfaces
are maintained by hand. That works until someone adds a required field to a response
model and forgets the other half, at which point the client reads `undefined` from a field
the server always sends, and the failure appears somewhere in rendering rather than at the
boundary where it was introduced.

This walks the generated OpenAPI schema and checks every response model that has a
same-named TypeScript interface. It deliberately compares only *required* fields:
optional ones may legitimately be omitted client-side when the UI has no use for them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_API_TS = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "lib" / "api.ts"


def _typescript_interfaces() -> dict[str, set[str]]:
    """Parse `export interface Name { ... }` blocks into name -> field names."""
    source = _API_TS.read_text(encoding="utf-8")
    interfaces: dict[str, set[str]] = {}
    for match in re.finditer(r"export interface (\w+)\s*\{(.*?)\n\}", source, re.S):
        name, body = match.group(1), match.group(2)
        interfaces[name] = set(re.findall(r"^\s*(\w+)\??\s*:", body, re.M))
    return interfaces


def _openapi_schemas() -> dict[str, dict]:
    from services.api.main import app

    return app.openapi()["components"]["schemas"]


def test_api_ts_is_parseable() -> None:
    """Guards the guard: a parse that silently matches nothing would pass everything."""
    interfaces = _typescript_interfaces()
    assert len(interfaces) > 40, f"only parsed {len(interfaces)} interfaces"
    assert "CandidateProfileResponse" in interfaces


def test_shared_types_are_actually_being_compared() -> None:
    """If the name-matching stops working, the drift test becomes vacuous."""
    shared = set(_openapi_schemas()) & set(_typescript_interfaces())
    assert len(shared) > 30, f"only {len(shared)} schemas matched a TS interface by name"


def test_no_required_response_field_is_missing_from_the_client() -> None:
    schemas = _openapi_schemas()
    interfaces = _typescript_interfaces()

    drift: list[str] = []
    for name, schema in schemas.items():
        if name not in interfaces:
            continue
        absent = set(schema.get("required", [])) - interfaces[name]
        if absent:
            drift.append(f"{name}: {sorted(absent)}")

    assert not drift, "TypeScript interfaces are missing required fields:\n" + "\n".join(drift)


@pytest.mark.parametrize(
    "schema_name,field",
    [
        # Fields added by this audit. Named explicitly so that removing one from either
        # side fails loudly here rather than only via the generic sweep above.
        ("CandidateProfileResponse", "stats_refresh_cooldown_seconds"),
        ("PresentationReportResponse", "plagiarism_checked"),
    ],
)
def test_audit_added_fields_exist_on_both_sides(schema_name: str, field: str) -> None:
    assert field in _openapi_schemas()[schema_name]["properties"]
    assert field in _typescript_interfaces()[schema_name]
