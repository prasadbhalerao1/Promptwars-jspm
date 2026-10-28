"""Small shared formatting helper — used by every rubric-scoring node so the LLM prompt
shape stays consistent across agents."""


def slides_text(slides: list[dict]) -> str:
    lines = []
    for s in slides:
        lines.append(
            f"Slide {s['index']}: title={s.get('title') or '(none)'}\n"
            f"body={s.get('body') or '(none)'}\nnotes={s.get('notes') or '(none)'}"
        )
    return "\n\n".join(lines)
