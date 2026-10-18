from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.models.resume import Resume
from app.utils.pdf_parser import extract_text_from_pdf
from app.core.exceptions import PDFParseError

ALLOWED_CONTENT_TYPE = "application/pdf"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def upload_and_parse_resume(file: UploadFile, db: Session) -> Resume:
    """Validate, parse, and persist a resume PDF.

    Returns the created Resume ORM object.
    """
    # ── Validate content type ──────────────────────────
    if file.content_type != ALLOWED_CONTENT_TYPE:
        raise PDFParseError(
            f"Only PDF files are allowed, got '{file.content_type}'"
        )

    # ── Read file bytes ────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise PDFParseError("File size exceeds 10 MB limit")

    # ── Parse PDF ──────────────────────────────────────
    raw_text = extract_text_from_pdf(file_bytes)

    if not raw_text:
        raise PDFParseError(
            "No text could be extracted from this PDF. "
            "The file may be a scanned image PDF — ensure Tesseract OCR is installed (chi_sim language pack required for Chinese)."
        )

    # ── Persist ────────────────────────────────────────
    resume = Resume(
        filename=file.filename or "unknown.pdf",
        raw_text=raw_text,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    return resume
