"""Candidate ingestion uploads must be type- and size-checked before they are read.

`POST /candidates/me/ingest/resume` and `.../certificate` called `await file.read()` with
no ceiling and no content-type check, then handed the bytes to pdfplumber/python-docx
(resume) or Pillow/Tesseract (certificate). An oversized upload was read fully into
memory and copied again into the queue payload; a wrong-typed one was only rejected deep
inside a parser, surfacing to the candidate as a failed background job rather than a
rejected upload. The presentation route has enforced both since it was written.
"""

from __future__ import annotations

from importlib import import_module

import pytest
from fastapi import HTTPException

candidates_router = import_module("services.api.modules.candidates.router")


class _Upload:
    """Minimal stand-in for Starlette's UploadFile."""

    def __init__(self, content_type: str | None, payload: bytes) -> None:
        self.content_type = content_type
        self.filename = "upload.bin"
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


async def _read(upload: _Upload, *, kind: str = "resume", max_mb: int = 1):
    allowed = (
        candidates_router._RESUME_CONTENT_TYPES
        if kind == "resume"
        else candidates_router._CERTIFICATE_CONTENT_TYPES
    )
    return await candidates_router._read_upload_or_400(
        upload, allowed_types=allowed, max_mb=max_mb, kind=kind
    )


@pytest.mark.parametrize(
    "content_type",
    ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
)
async def test_supported_resume_types_pass(content_type: str) -> None:
    assert await _read(_Upload(content_type, b"%PDF-1.7 ...")) == b"%PDF-1.7 ..."


@pytest.mark.parametrize("content_type", ["image/png", "image/jpeg"])
async def test_supported_certificate_types_pass(content_type: str) -> None:
    assert await _read(_Upload(content_type, b"\x89PNG"), kind="certificate") == b"\x89PNG"


@pytest.mark.parametrize(
    "content_type",
    ["application/zip", "text/html", "application/x-msdownload", None],
)
async def test_unsupported_type_is_rejected(content_type) -> None:
    with pytest.raises(HTTPException) as exc:
        await _read(_Upload(content_type, b"whatever"))
    assert exc.value.status_code == 400
    assert "unsupported_resume_type" in exc.value.detail


async def test_image_is_not_accepted_as_a_resume() -> None:
    """The two allowlists are distinct; a certificate image is not a parseable resume."""
    with pytest.raises(HTTPException):
        await _read(_Upload("image/png", b"\x89PNG"))


async def test_oversized_upload_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await _read(_Upload("application/pdf", b"x" * (2 * 1024 * 1024)), max_mb=1)
    assert exc.value.status_code == 413
    assert "max 1MB" in exc.value.detail


async def test_upload_at_the_limit_is_accepted() -> None:
    payload = b"x" * (1024 * 1024)
    assert await _read(_Upload("application/pdf", payload), max_mb=1) == payload


async def test_empty_upload_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        await _read(_Upload("application/pdf", b""))
    assert exc.value.status_code == 400
    assert exc.value.detail == "empty_file"
