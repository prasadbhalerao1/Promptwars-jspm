"""Regression tests for `prompts_loader` and the prompt files themselves.

These exist because the loader previously failed *silently*: it used
`string.Template.substitute`, which only understands `$name`, while every prompt file
uses `{name}`. Nothing raised — the LLM simply received the literal text `"{query}"`
where the recruiter's query should have been, and the resulting answers looked
plausible enough that no test or reviewer caught it. A prompt that never interpolates
is the kind of bug that only surfaces as "the AI seems a bit off".
"""

import re
from pathlib import Path

import pytest

from services.agents.prompts_loader import load_prompt

PROMPTS_ROOT = Path(__file__).resolve().parent.parent
ALL_PROMPTS = sorted(
    (p.parent.parent.name, p.stem) for p in PROMPTS_ROOT.glob("*/prompts/*.md")
)
PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _placeholders(agent: str, name: str) -> list[str]:
    """Real placeholders in a prompt file, excluding escaped literal braces.

    `{{name}}` is the loader's escape for a literal `{name}` in prompt prose — needed
    because examples inside prompts contain real code (a FastAPI route
    `@app.get("/items/{item_id}")`, a JSON template) whose braces must reach the model
    verbatim rather than being treated as template variables. Blanking the escaped forms
    before scanning keeps this test asserting on actual placeholders.
    """
    text = (PROMPTS_ROOT / agent / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    text = text.replace("{{", "<ESC>").replace("}}", "<ESC>")
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def test_prompt_files_exist():
    assert ALL_PROMPTS, "no prompt files discovered — check the glob"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_every_placeholder_is_substituted(agent: str, name: str):
    """The core regression: supplied values must actually reach the rendered prompt."""
    names = _placeholders(agent, name)
    values = {n: f"<<{n.upper()}>>" for n in names}
    rendered = load_prompt(agent, name, **values)

    for n in names:
        assert f"{{{n}}}" not in rendered, f"{agent}/{name}: '{{{n}}}' left unsubstituted"
        assert values[n] in rendered, f"{agent}/{name}: value for '{n}' never appeared"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_section_headings_survive(agent: str, name: str):
    """`## Examples`, `## Rules` etc. must reach the model.

    The old loader dropped every line starting with `#` to remove the H1 title, which
    also stripped all section headings — the instructions arrived as one undifferentiated
    wall of text with the examples unlabelled.
    """
    source = (PROMPTS_ROOT / agent / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    rendered = load_prompt(agent, name, **{n: "x" for n in _placeholders(agent, name)})

    for heading in [ln for ln in source.split("\n") if ln.startswith("## ")]:
        assert heading in rendered, f"{agent}/{name}: lost heading {heading!r}"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_h1_title_is_stripped(agent: str, name: str):
    """The H1 names the file for humans; it's noise for the model."""
    source = (PROMPTS_ROOT / agent / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    first = source.split("\n")[0]
    if not first.startswith("# "):
        pytest.skip("prompt has no H1 title")
    rendered = load_prompt(agent, name, **{n: "x" for n in _placeholders(agent, name)})
    assert not rendered.startswith(first)


def test_missing_variable_raises_rather_than_shipping_placeholder():
    """Failing loudly beats sending `{query}` to a paid model."""
    with pytest.raises(ValueError, match="Missing variable"):
        load_prompt("supervisor", "classifier")


def test_json_examples_are_not_mangled():
    """Prompts embed JSON examples; quoted keys must not be read as placeholders."""
    rendered = load_prompt("candidate_intelligence", "resume_extraction", resume_text="X")
    assert '"name": "Go"' in rendered
    assert '"years": 2.5' in rendered


def test_literal_braces_can_be_escaped(monkeypatch):
    """`{{x}}` renders as `{x}`, so a prompt can show placeholder syntax literally."""
    from services.agents import prompts_loader

    monkeypatch.setattr(
        prompts_loader,
        "_load_prompt_text",
        lambda agent, name: "Literal {{braces}} and real {value}.",
    )

    out = prompts_loader.load_prompt("any", "any", value="V")
    assert "Literal {braces} and real V." == out


def test_unknown_prompt_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_prompt("supervisor", "no_such_prompt")
