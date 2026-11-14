"""Dataset preview helpers for BYO wizard (parse + redaction)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from traceiq.api.deps import AuthUser, db_session, require_role
from traceiq.api.errors import AppError
from traceiq.auth.rbac import Role
from traceiq.ingest.pipeline import ingest_file
from traceiq.safety.redact import redaction_preview

router = APIRouter(prefix="/datasets", tags=["datasets"])


class PreviewBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=40_000_000)
    filename: str = "upload.log"


@router.post("/preview")
def preview_dataset(
    body: PreviewBody,
    user: AuthUser = Depends(require_role(Role.INVESTIGATOR)),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    _ = (user, session)
    sample = body.text[:4096]
    if "\x00" in sample:
        raise AppError(
            400,
            "Bad Request",
            "File looks binary. Upload a text log, or strip null bytes and retry.",
        )
    # Large industry slices: preview on a head sample so the wizard stays responsive.
    preview_text = body.text
    sampled = False
    if len(body.text) > 1_500_000:
        preview_text = "\n".join(body.text.splitlines()[:8000]) + "\n"
        sampled = True
    suffix = Path(body.filename).suffix or ".log"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=suffix, delete=False
    ) as tmp:
        tmp.write(preview_text)
        tmp_path = Path(tmp.name)
    try:
        result = ingest_file(tmp_path, dry_run=True)
    finally:
        tmp_path.unlink(missing_ok=True)

    redaction = redaction_preview(body.text[:50_000])
    report = result.report.to_dict()
    if sampled:
        report["note"] = (
            "Parse preview sampled the first ~8000 lines; full file is used on incident create."
        )
    return {
        "filename": body.filename,
        "detected_format": result.report.format,
        "detect_confidence": result.report.detect_confidence,
        "parse_report": report,
        "redaction": redaction,
        "bytes": len(body.text.encode("utf-8")),
        "preview_sampled": sampled,
    }
