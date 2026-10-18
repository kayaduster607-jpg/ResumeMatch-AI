from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.exceptions import AppException
from app.models.resume import Resume
from app.models.analysis_task import AnalysisTask
from app.models.match_report import MatchReport
from app.models.interview_question import InterviewQuestion
from app.models.rewritten_resume import RewrittenResume
from app.services.resume_service import upload_and_parse_resume
from app.services.resume_parse_service import parse_resume
from app.schemas.resume import ResumeUploadResponse, ResumeUploadData
from app.schemas.resume_parse import ResumeParseResponse, ResumeParseData

router = APIRouter()

TEXT_PREVIEW_LEN = 500


class ResumeListItem(BaseModel):
    id: int
    filename: str
    text_preview: str = ""


class ResumeListResponse(BaseModel):
    success: bool
    data: list[ResumeListItem]


@router.get("/list", response_model=ResumeListResponse)
def list_resumes(db: Session = Depends(get_db)):
    resumes = db.query(Resume).order_by(Resume.id.desc()).all()
    items = [
        ResumeListItem(
            id=r.id,
            filename=r.filename,
            text_preview=(r.raw_text or "")[:200],
        )
        for r in resumes
    ]
    return ResumeListResponse(success=True, data=items)


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    resume = await upload_and_parse_resume(file, db)  # async file.read() inside
    preview = resume.raw_text[:TEXT_PREVIEW_LEN] if resume.raw_text else ""

    return ResumeUploadResponse(
        success=True,
        data=ResumeUploadData(
            resume_id=resume.id,
            filename=resume.filename,
            text_preview=preview,
        ),
    )


@router.post("/{resume_id}/parse", response_model=ResumeParseResponse)
def parse_resume_endpoint(
    resume_id: int,
    db: Session = Depends(get_db),
):
    parsed = parse_resume(resume_id, db)

    return ResumeParseResponse(
        success=True,
        data=ResumeParseData(
            resume_id=resume_id,
            parsed_json=parsed,
        ),
    )


def _delete_analysis_tasks(db: Session, task_ids: list[int]) -> None:
    if not task_ids:
        return
    db.query(InterviewQuestion).filter(InterviewQuestion.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(RewrittenResume).filter(RewrittenResume.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(MatchReport).filter(MatchReport.task_id.in_(task_ids)).delete(synchronize_session=False)
    db.query(AnalysisTask).filter(AnalysisTask.id.in_(task_ids)).delete(synchronize_session=False)


@router.delete("/{resume_id}")
def delete_resume_endpoint(
    resume_id: int,
    db: Session = Depends(get_db),
):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if resume is None:
        raise AppException("简历不存在或已删除。", code="RESUME_NOT_FOUND", status_code=404)

    task_ids = [row[0] for row in db.query(AnalysisTask.id).filter(AnalysisTask.resume_id == resume_id).all()]
    _delete_analysis_tasks(db, task_ids)
    db.delete(resume)
    db.commit()
    return {"success": True, "message": "已删除简历及相关分析、改写、面试记录。"}
