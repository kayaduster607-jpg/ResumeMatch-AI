from sqlalchemy.orm import Session

from app.models.job_description import JobDescription
from app.schemas.jd import JDCreateRequest
from app.core.exceptions import AppException


def create_jd(req: JDCreateRequest, db: Session) -> JobDescription:
    """Persist a raw JD to the database."""
    if not req.raw_text or not req.raw_text.strip():
        raise AppException("JD raw_text cannot be empty", code="EMPTY_JD_TEXT")

    jd = JobDescription(
        title=req.title or None,
        company=req.company or None,
        raw_text=req.raw_text.strip(),
    )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return jd
