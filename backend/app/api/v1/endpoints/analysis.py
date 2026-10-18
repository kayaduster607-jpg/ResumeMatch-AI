from fastapi import APIRouter, Depends
from fastapi.responses import Response, HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.analysis_task import AnalysisTask
from app.models.match_report import MatchReport
from app.models.interview_question import InterviewQuestion
from app.models.rewritten_resume import RewrittenResume
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisRunResponse,
    AnalysisDetailResponse,
    AnalysisHistoryResponse,
    AnalysisHistoryItem,
)
from app.schemas.rewrite import RewriteResponse, RewriteData
from app.schemas.rewrite_resume import SaveEditedResumeRequest
from app.schemas.interview import InterviewQuestionsResponse, InterviewQuestionsData
from app.schemas.mock_interview import MockInterviewRequest, MockInterviewResponse
from app.schemas.report import ReportResponse
from app.services.analysis_service import run_analysis, get_analysis_detail, list_analysis_history
from app.services.rewrite_service import generate_rewrites
from app.services.resume_rewrite_service import generate_full_rewrite, get_rewrite, save_edited_rewrite, export_rewritten_resume_pdf, export_rewritten_resume_docx
from app.services.interview_question_service import generate_interview_questions
from app.services.mock_interview_service import score_answer
from app.services.report_service import generate_full_report
from app.services.export_service import export_report_docx, export_report_html, export_report_pdf

router = APIRouter()


def _model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


# ── Core analysis ──────────────────────────────────────

@router.post("/run", response_model=AnalysisRunResponse)
def run_analysis_endpoint(
    req: AnalysisRequest,
    db: Session = Depends(get_db),
):
    result = run_analysis(req.resume_id, req.jd_id, db)
    return AnalysisRunResponse(success=True, data=result)


@router.get("/history/list", response_model=AnalysisHistoryResponse)
def list_history_endpoint(
    db: Session = Depends(get_db),
):
    items = list_analysis_history(db)
    history = [AnalysisHistoryItem(**item) for item in items]
    return AnalysisHistoryResponse(success=True, data=history, total=len(history))


@router.delete("/{task_id}")
def delete_analysis_endpoint(task_id: int, db: Session = Depends(get_db)):
    task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
    if task is None:
        return {"success": True, "message": "分析记录不存在或已删除"}
    db.query(InterviewQuestion).filter(InterviewQuestion.task_id == task_id).delete(synchronize_session=False)
    db.query(RewrittenResume).filter(RewrittenResume.task_id == task_id).delete(synchronize_session=False)
    db.query(MatchReport).filter(MatchReport.task_id == task_id).delete(synchronize_session=False)
    db.delete(task)
    db.commit()
    return {"success": True, "message": "分析记录已删除"}


@router.get("/{task_id}", response_model=AnalysisDetailResponse)
def get_analysis_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    result = get_analysis_detail(task_id, db)
    return AnalysisDetailResponse(success=True, data=result)


# ── Rewrite suggestions (project-level) ──────────────────

@router.post("/{task_id}/rewrite", response_model=RewriteResponse)
def rewrite_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    result = generate_rewrites(task_id, db)
    return RewriteResponse(success=True, data=result)


# ── Full resume rewrite (AI-powered) ─────────────────────

@router.post("/{task_id}/full-rewrite")
def full_rewrite_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    result = generate_full_rewrite(task_id, db)
    return {
        "success": True,
        "data": _model_to_dict(result),
    }


@router.get("/{task_id}/full-rewrite")
def get_full_rewrite_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    result = get_rewrite(task_id, db)
    if result is None:
        return {"success": False, "data": None, "message": "No rewrite found for this task"}
    return {"success": True, "data": _model_to_dict(result)}


@router.put("/{task_id}/full-rewrite")
def save_full_rewrite_endpoint(
    task_id: int,
    req: SaveEditedResumeRequest,
    db: Session = Depends(get_db),
):
    save_edited_rewrite(task_id, req.edited_text, db)
    return {"success": True, "message": "Edited resume saved"}


@router.get("/{task_id}/full-rewrite/export/pdf")
def export_full_rewrite_pdf_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    pdf_bytes = export_rewritten_resume_pdf(task_id, db)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=rewritten_resume_{task_id}.pdf"},
    )


@router.get("/{task_id}/full-rewrite/export/word")
def export_full_rewrite_word_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    docx_bytes = export_rewritten_resume_docx(task_id, db)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=rewritten_resume_{task_id}.docx"},
    )


# ── Interview questions ────────────────────────────────

@router.post("/{task_id}/interview-questions", response_model=InterviewQuestionsResponse)
def interview_questions_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    result = generate_interview_questions(task_id, db)
    return InterviewQuestionsResponse(success=True, data=result)


# ── Full report ────────────────────────────────────────

@router.get("/{task_id}/report", response_model=ReportResponse)
def report_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    result = generate_full_report(task_id, db)
    return ReportResponse(success=True, data=result)


# ── Export ──────────────────────────────────────────────

@router.get("/{task_id}/export/word")
def export_word_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    docx_bytes = export_report_docx(task_id, db)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=report_{task_id}.docx"},
    )


@router.get("/{task_id}/export/pdf")
def export_pdf_endpoint(
    task_id: int,
    db: Session = Depends(get_db),
):
    pdf_bytes = export_report_pdf(task_id, db)
    # Check if we got actual PDF bytes (starts with %PDF) or HTML fallback
    if pdf_bytes[:4] == b"%PDF":
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=report_{task_id}.pdf"},
        )
    else:
        return HTMLResponse(content=pdf_bytes.decode("utf-8"))
