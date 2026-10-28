"""FR-5.1 — render generated resume content into an ATS-friendly PDF.

ATS-friendly per doc 01 §9 ("WeasyPrint (HTML/CSS -> PDF, best for ATS-clean resumes)"):
plain single-column HTML, no tables, no floated/graphic layouts, standard heading tags
so ATS parsers can walk the DOM in reading order.

WeasyPrint's Python package is a real dependency (installed in services/api/.venv), but
importing it requires native GTK/Pango/cairo libraries that aren't present on every dev
machine (confirmed missing on this Windows sandbox: `OSError: cannot load library
'libgobject-2.0-0'`). The import is deferred into the render call so a missing native
lib doesn't crash the whole API process at import time — callers get a clear
`PdfGenerationUnavailable` instead, same pattern as `ResumeExtractionUnavailable` /
`StorageUnavailable` elsewhere in this module.
"""

import html


class PdfGenerationUnavailable(RuntimeError):
    """Raised when WeasyPrint (or its native GTK/Pango/cairo dependencies) can't load."""


def _resume_html(content: dict) -> str:
    def esc(value: object) -> str:
        return html.escape(str(value)) if value is not None else ""

    skills = content.get("skills") or []
    experience = content.get("experience") or []
    education = content.get("education") or []

    experience_html = "".join(
        f"""
        <section class="entry">
          <h3>{esc(job.get('title'))}{f" — {esc(job.get('company'))}" if job.get('company') else ""}</h3>
          {f'<p class="meta">{esc(job.get("years"))}</p>' if job.get('years') else ''}
          <ul>{''.join(f"<li>{esc(b)}</li>" for b in job.get('bullets') or [])}</ul>
        </section>
        """
        for job in experience
    )
    education_html = "".join(
        f"""
        <section class="entry">
          <h3>{esc(edu.get('institution'))}</h3>
          <p class="meta">{esc(edu.get('degree'))} {esc(edu.get('year'))}</p>
        </section>
        """
        for edu in education
    )

    # Deliberately no <table>, no CSS grid/float layout, no images — plain block flow
    # only, so ATS parsers extract text in the same order a human reads it.
    return f"""
    <html>
    <head><meta charset="utf-8"><style>
      body {{ font-family: Arial, Helvetica, sans-serif; color: #12161c; font-size: 11pt; }}
      h1 {{ font-size: 18pt; margin-bottom: 0; }}
      h2 {{ font-size: 12pt; border-bottom: 1px solid #5b6472; margin-top: 18pt; }}
      h3 {{ font-size: 11pt; margin-bottom: 2pt; }}
      .meta {{ color: #5b6472; font-size: 9.5pt; margin: 0 0 4pt 0; }}
      ul {{ margin: 4pt 0; padding-left: 16pt; }}
      .skills {{ margin: 4pt 0; }}
    </style></head>
    <body>
      <h1>{esc(content.get('headline'))}</h1>
      <p>{esc(content.get('summary'))}</p>
      <h2>Skills</h2>
      <p class="skills">{esc(', '.join(skills))}</p>
      <h2>Experience</h2>
      {experience_html}
      <h2>Education</h2>
      {education_html}
    </body>
    </html>
    """


def render_resume_pdf(content: dict) -> bytes:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise PdfGenerationUnavailable(
            "WeasyPrint could not be loaded (missing native GTK/Pango/cairo "
            f"dependencies): {exc}"
        ) from exc

    return HTML(string=_resume_html(content)).write_pdf()
