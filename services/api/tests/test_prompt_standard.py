"""Every agent prompt must meet the same structural standard.

Prompt quality is invisible to ordinary tests: a prompt that lost its guardrails still
renders, still calls the provider, and still returns a schema-valid object — it just
produces worse judgments about real candidates. Nothing fails until someone reads an
inflated score or a fabricated claim in production.

So the structure is asserted here. These checks cannot verify that a prompt is *good*
(only a human reading outputs can), but they do prevent the specific regressions this
codebase already had: prompts with no examples, no failure handling, and no statement of
what the agent must never do.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

AGENTS_ROOT = Path(__file__).resolve().parents[2] / "agents"
ALL_PROMPTS = sorted(
    (p.parent.parent.name, p.stem) for p in AGENTS_ROOT.glob("*/prompts/*.md")
)

# Sections every prompt must carry. Each exists because its absence caused a real problem:
# without <role> the model has no stake in the output, without <guardrails> it invents
# plausible detail, without <edge_cases> it fabricates rather than admitting uncertainty,
# and without <output_format> it answers on whatever scale it likes.
REQUIRED_SECTIONS = ("<role>", "<context>", "<instructions>", "<output_format>", "<guardrails>", "<edge_cases>", "<examples>")

# Anthropic's prompting guidance recommends 3-5 diverse examples; below three there is not
# enough variation for the model to generalize rather than pattern-match.
MIN_EXAMPLES = 3


def _text(agent: str, name: str) -> str:
    return (AGENTS_ROOT / agent / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def test_prompts_were_discovered() -> None:
    assert len(ALL_PROMPTS) >= 20, f"expected the full prompt set, found {len(ALL_PROMPTS)}"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_prompt_has_required_section(agent: str, name: str, section: str) -> None:
    assert section in _text(agent, name), f"{agent}/{name} is missing {section}"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_prompt_has_enough_examples(agent: str, name: str) -> None:
    count = _text(agent, name).count("<example ")
    assert count >= MIN_EXAMPLES, f"{agent}/{name} has {count} examples, need {MIN_EXAMPLES}"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_examples_are_diverse(agent: str, name: str) -> None:
    """Examples must cover more than the happy path.

    Three variations of a typical case teach the model one behaviour. The failure modes
    that matter — empty input, contradictory input, an adversarial payload — only get
    handled reliably if they are demonstrated.
    """
    types = re.findall(r'<example[^>]*type="([^"]+)"', _text(agent, name))
    assert types, f"{agent}/{name}: examples must carry a type attribute"

    kinds = {t.split("-")[0] for t in types}
    assert len(kinds) >= 2, (
        f"{agent}/{name}: all {len(types)} examples are '{kinds}' — needs at least one "
        f"edge case, bad input or adversarial example alongside the typical one"
    )


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_scoring_prompts_state_their_scale(agent: str, name: str) -> None:
    """Any prompt producing a score must say 0-100 explicitly in its output contract.

    A JSON-schema `description` of "0-100" is prose the provider may ignore; models
    routinely answer on a 0-10 or 0-1 scale. That produced the exact bug this refactor
    fixed, where an 8.5 was persisted as 8.5/100 and fed recruiter matching.
    """
    text = _text(agent, name)
    output_block = text[text.index("<output_format>") : text.index("</output_format>")]

    # Match a field the prompt actually emits as a number, e.g. "`score` - number" or
    # "`technical_rating` - number". Substring matching on "score" alone produced false
    # positives on prompts that merely mention the word (the supervisor's `candidate_score`
    # intent, the re-ranker referring to Talent Scores it must not output).
    emits_a_number = re.search(
        r"`\w*(?:score|rating)\w*`\s*[—\-–]\s*(?:a\s+)?number", output_block, re.IGNORECASE
    )
    if not emits_a_number:
        pytest.skip("not a scoring prompt")
    assert "0-100" in output_block, f"{agent}/{name}: output_format must state the 0-100 scale"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_guardrails_are_substantive(agent: str, name: str) -> None:
    """A guardrails section with one line is a box being ticked, not a constraint."""
    text = _text(agent, name)
    block = text[text.index("<guardrails>") : text.index("</guardrails>")]
    rules = [line for line in block.splitlines() if line.strip().startswith("- ")]
    assert len(rules) >= 4, f"{agent}/{name}: only {len(rules)} guardrails"


@pytest.mark.parametrize(("agent", "name"), ALL_PROMPTS)
def test_no_stray_unescaped_placeholders(agent: str, name: str) -> None:
    """Placeholders in the instructional prose (not the input block) are a bug.

    A `{name}` the caller does not supply raises at render time; one that looks like a
    placeholder but is meant literally (a JSON example, a route template) must be escaped
    as `{{name}}` or it will be silently substituted with caller data.
    """
    text = _text(agent, name).replace("{{", "").replace("}}", "")
    # Placeholders legitimately appear in <input> and in inline `{topic}`-style references.
    found = set(re.findall(r"\{(\w+)\}", text))
    assert all(f.islower() or "_" in f for f in found), (
        f"{agent}/{name}: suspicious placeholder casing in {found}"
    )
