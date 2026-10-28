"""Certificate OCR — mechanical baseline (Tesseract), no LLM dependency. FR-1.4.

Doc 01 §4 allows a Claude-vision fallback for low-quality scans; that path is intentionally
left for a follow-up since it needs `ANTHROPIC_API_KEY`. This baseline always runs and simply
flags low-confidence extractions for manual review, per the doc's own stated behavior.
"""

import io
import re
from dataclasses import dataclass

import pytesseract
from PIL import Image

_DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b[A-Z][a-z]+ \d{1,2},? \d{4})\b")
_CREDENTIAL_RE = re.compile(r"\b(?:credential|cert(?:ificate)? id)[:\s]*([A-Za-z0-9\-]+)", re.IGNORECASE)


@dataclass
class CertificateExtraction:
    raw_text: str
    title: str | None
    issue_date: str | None
    credential_id: str | None
    ocr_confidence: float


def extract_certificate(file_bytes: bytes) -> CertificateExtraction:
    image = Image.open(io.BytesIO(file_bytes))
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    words = [w for w in data["text"] if w.strip()]
    confidences = [int(c) for c in data["conf"] if c not in ("-1", "") and int(c) >= 0]
    raw_text = " ".join(words)
    ocr_confidence = (sum(confidences) / len(confidences) / 100) if confidences else 0.0

    date_match = _DATE_RE.search(raw_text)
    credential_match = _CREDENTIAL_RE.search(raw_text)
    # Heuristic: the longest line is usually the certificate title (mechanical baseline
    # only — flagged low-confidence, per doc 01 §4, until a vision-model fallback exists).
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    title = max(lines, key=len) if lines else None

    return CertificateExtraction(
        raw_text=raw_text,
        title=title,
        issue_date=date_match.group(0) if date_match else None,
        credential_id=credential_match.group(1) if credential_match else None,
        ocr_confidence=round(ocr_confidence, 2),
    )
