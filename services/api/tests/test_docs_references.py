"""Documentation must not point at files that no longer exist.

The docs are dense with `path/to/file.py` references, and they are the main way someone
navigates from "what does this do" to the code. When a module moves, the reference rots
silently — nothing fails, and the next reader is sent to a file that isn't there.

A sweep in 2026-08 found 32 broken references: modules that moved between `tools/` and
`nodes/`, a graph renamed `graph.py` -> `matching_graph.py`, a node
(`topic_planning.py`) that never existed, a migration folded into the squashed baseline,
and a whole package (`packages/prompts/`) that had been deleted.

This also guards `.agents/decisions.md`, which 37 source files cite as the record of why
the architecture is shaped the way it is — and which had gone missing entirely, so every
one of those pointers dead-ended.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
# The architecture docs are tracked in `Documentation/`; README/SETUP and the decisions
# record live under the local-only `dev/` folder. Each check below uses whichever copy the
# checkout actually has, and the module skips only when there are no docs at all.
_DOCS = _ROOT / "dev"
_DOC_DIR = next(
    (d for d in (_ROOT / "Documentation", _DOCS / "Documentation") if d.is_dir() and any(d.glob("*.md"))),
    None,
)

pytestmark = pytest.mark.skipif(_DOC_DIR is None, reason="no Documentation/ folder present")

# Docs that intentionally reference deleted paths: historical records of a migration whose
# whole subject is what was removed. Each carries a banner saying so.
_HISTORICAL = {"PROMPTS_MIGRATION.md"}

# Paths a doc may name while explicitly describing them as gone or not-yet-built.
#
# Two distinct cases, both legitimate:
#   * `packages/prompts/*` — deleted, and named in a "what this replaced" section. Saying
#     what was removed requires naming it.
#   * the deployment configs — `Hackathon_Submission.md` §9 is a deployment *design*, and
#     carries a scope note saying these are proposed rather than committed files.
#
# Kept as a narrow explicit list rather than a whole-file skip: a doc that legitimately
# discusses one removed path should still be checked for every other path it names.
_KNOWN_ABSENT = {
    "packages/prompts/registry.py",
    "packages/prompts/templates",
    "apps/web/vercel.json",
    "apps/web/next.config.mobile.ts",
    "apps/web/capacitor.config.ts",
    "apps/web/android/app/src/main/AndroidManifest.xml",
    "infra/nginx.conf",
}

# `path/to/thing.py`, optionally with ::Symbol or :line-range suffixes.
_PATH_RE = re.compile(
    r"`((?:apps|services|packages|scripts|infra)/[A-Za-z0-9_./\[\]-]+?)"
    r"(?:::[A-Za-z_]\w*)?(?::\d+(?:-\d+)?)?`"
)


def _doc_files() -> list[Path]:
    if _DOC_DIR is None:
        return []
    docs = sorted(_DOC_DIR.rglob("*.md"))
    docs += [p for p in (_DOCS / "README.md", _DOCS / "SETUP.md") if p.exists()]
    return docs


def test_the_scanner_finds_something() -> None:
    """Guards the guard: a regex that matches nothing would pass every test below."""
    total = sum(len(_PATH_RE.findall(d.read_text(encoding="utf-8", errors="replace"))) for d in _doc_files())
    assert total > 100, f"only found {total} path references; the scanner is probably broken"


@pytest.mark.parametrize("doc", _doc_files(), ids=lambda p: p.name)
def test_documented_paths_exist(doc: Path) -> None:
    if doc.name in _HISTORICAL:
        pytest.skip(f"{doc.name} is a historical record of removed files")

    text = doc.read_text(encoding="utf-8", errors="replace")
    broken = sorted(
        {
            ref
            for ref in (m.group(1).rstrip("/.,") for m in _PATH_RE.finditer(text))
            if not ref.endswith(".md")
            and ref not in _KNOWN_ABSENT
            and not (_ROOT / ref).exists()
        }
    )
    assert not broken, f"{doc.name} references paths that do not exist: {broken}"


def test_the_architecture_decisions_record_exists() -> None:
    """37 source files say "see .agents/decisions.md". It must be there to see."""
    decisions = _DOCS / ".agents" / "decisions.md"
    assert decisions.exists(), (
        "code across both languages cites .agents/decisions.md as the record of why the "
        "architecture is shaped the way it is; without it every one of those pointers "
        "dead-ends"
    )
    assert len(decisions.read_text(encoding="utf-8")) > 2000, "decisions record is a stub"


def test_exemptions_are_still_needed() -> None:
    """An exemption for a path that now exists is dead weight that hides real breakage."""
    resurrected = sorted(ref for ref in _KNOWN_ABSENT if (_ROOT / ref).exists())
    assert not resurrected, (
        f"these paths exist now and should be removed from _KNOWN_ABSENT: {resurrected}"
    )


def test_historical_docs_are_labelled_as_such() -> None:
    """A doc exempted from the path check must say why, or the exemption hides real rot."""
    for name in _HISTORICAL:
        matches = list((_DOCS / "Documentation").rglob(name))
        assert matches, f"{name} is exempted but does not exist"
        head = matches[0].read_text(encoding="utf-8")[:1200].lower()
        assert "historical" in head or "superseded" in head, (
            f"{name} skips the broken-path check but does not tell the reader it is stale"
        )
