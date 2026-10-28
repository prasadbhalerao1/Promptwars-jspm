"""Deterministic static analysis — FR-1.3, doc 03 §5's "Static Analysis Agent | tools
only". No LLM, no network. Runs on the candidate's submitted source text directly (never
executed, only parsed/scanned) — the sandbox-security boundary doc 03 §5 requires.
"""

import ast
import tempfile
from pathlib import Path

from radon.complexity import cc_visit
from radon.raw import analyze as radon_raw_analyze


def _radon_report(source: str) -> dict:
    try:
        blocks = cc_visit(source)
        complexities = [b.complexity for b in blocks]
        raw = radon_raw_analyze(source)
        return {
            "avg_complexity": round(sum(complexities) / len(complexities), 1) if complexities else None,
            "max_complexity": max(complexities) if complexities else None,
            "loc": raw.loc,
            "sloc": raw.sloc,
        }
    except SyntaxError as exc:
        return {"error": f"syntax_error: {exc}"}


def _lizard_report(source: str) -> dict:
    import lizard

    # lizard's analyzer works off files, not strings — write to a scratch temp file
    # rather than shelling out or holding the source in a persistent location.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(source)
        path = f.name
    try:
        result = lizard.analyze_file(path)
        return {
            "function_count": len(result.function_list),
            "avg_cyclomatic_complexity": round(
                sum(fn.cyclomatic_complexity for fn in result.function_list) / len(result.function_list), 1
            )
            if result.function_list
            else None,
            "nloc": result.nloc,
        }
    finally:
        Path(path).unlink(missing_ok=True)


def _bandit_report(source: str) -> dict:
    from bandit.core import config as bandit_config
    from bandit.core import manager as bandit_manager

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(source)
        path = f.name
    try:
        conf = bandit_config.BanditConfig()
        mgr = bandit_manager.BanditManager(conf, "file")
        mgr.discover_files([path])
        mgr.run_tests()
        issues = [
            {"severity": issue.severity, "confidence": issue.confidence, "text": issue.text}
            for issue in mgr.get_issue_list()
        ]
        return {"issue_count": len(issues), "issues": issues[:10]}
    except Exception as exc:  # bandit's manager can raise on malformed input — never crash the pipeline over it
        return {"error": str(exc)}
    finally:
        Path(path).unlink(missing_ok=True)


def run_static_analysis(source: str) -> dict:
    """Best-effort across all three tools — a syntactically invalid submission still
    gets whatever partial signal is possible (bandit/lizard tolerate more malformed
    input than radon's AST-based complexity visitor) rather than failing the whole
    pipeline over one tool's parse error."""
    try:
        ast.parse(source)
        syntax_valid = True
    except SyntaxError:
        syntax_valid = False

    return {
        "syntax_valid": syntax_valid,
        "radon": _radon_report(source),
        "lizard": _lizard_report(source) if syntax_valid else {"skipped": "invalid syntax"},
        "bandit": _bandit_report(source) if syntax_valid else {"skipped": "invalid syntax"},
    }
