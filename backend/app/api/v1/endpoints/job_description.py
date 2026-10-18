from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.job_description import JobDescription
from app.models.analysis_task import AnalysisTask
from app.models.match_report import MatchReport
from app.models.interview_question import InterviewQuestion
from app.models.rewritten_resume import RewrittenResume
from app.schemas.jd import (
    JDCreateRequest,
    JDCreateResponse,
    JDCreateData,
    JDParseResponse,
    JDParseData,
    PlatformLoginBrowserRequest,
    PlatformLoginResponse,
    PlatformLoginStateData,
    PlatformSearchRequest,
    PlatformSearchResponse,
    PlatformSearchData,
)
from app.services.jd_service import create_jd
from app.services.jd_parse_service import parse_jd
from app.services.platform_crawler_service import search_platform_jobs
from app.services.playwright_browser_worker import get_browser_worker
from app.utils.model_dump import model_to_dict

router = APIRouter()


class JDListItem(BaseModel):
    id: int
    title: str = ""
    company: str = ""
    source: str = "手动输入"


class JDListResponse(BaseModel):
    success: bool
    data: list[JDListItem]


@router.get("/list", response_model=JDListResponse)
def list_jds(db: Session = Depends(get_db)):
    jds = db.query(JobDescription).order_by(JobDescription.id.desc()).all()
    items = []
    for jd in jds:
        source = "手动输入"
        if jd.raw_text and "招聘平台" in jd.raw_text:
            # Try to extract platform name from raw_text
            for platform_name in ["BOSS直聘", "猎聘", "智联招聘", "前程无忧"]:
                if platform_name in jd.raw_text:
                    source = platform_name
                    break
        items.append(JDListItem(id=jd.id, title=jd.title or "", company=jd.company or "", source=source))
    return JDListResponse(success=True, data=items)




@router.delete("/{jd_id}")
def delete_jd_endpoint(jd_id: int, db: Session = Depends(get_db)):
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if jd is None:
        return {"success": True, "message": "岗位不存在或已删除"}
    task_ids = [x[0] for x in db.query(AnalysisTask.id).filter(AnalysisTask.jd_id == jd_id).all()]
    if task_ids:
        db.query(InterviewQuestion).filter(InterviewQuestion.task_id.in_(task_ids)).delete(synchronize_session=False)
        db.query(RewrittenResume).filter(RewrittenResume.task_id.in_(task_ids)).delete(synchronize_session=False)
        db.query(MatchReport).filter(MatchReport.task_id.in_(task_ids)).delete(synchronize_session=False)
        db.query(AnalysisTask).filter(AnalysisTask.id.in_(task_ids)).delete(synchronize_session=False)
    db.delete(jd)
    db.commit()
    return {"success": True, "message": "岗位及关联分析记录已删除"}


@router.post("", response_model=JDCreateResponse)
def create_jd_endpoint(
    req: JDCreateRequest,
    db: Session = Depends(get_db),
):
    jd = create_jd(req, db)

    return JDCreateResponse(
        success=True,
        data=JDCreateData(jd_id=jd.id),
    )


@router.post("/{jd_id}/parse", response_model=JDParseResponse)
def parse_jd_endpoint(
    jd_id: int,
    db: Session = Depends(get_db),
):
    parsed = parse_jd(jd_id, db)

    return JDParseResponse(
        success=True,
        data=JDParseData(
            jd_id=jd_id,
            parsed_json=parsed,
        ),
    )


# ── Recruitment platform crawler ──────────────────────

@router.post("/platforms/open-login-browser", response_model=PlatformLoginResponse)
def open_platform_login_browser(req: PlatformLoginBrowserRequest):
    data = get_browser_worker().open_login_pages(req.platforms)
    return PlatformLoginResponse(success=True, data=PlatformLoginStateData(**data))


@router.post("/platforms/save-login-state", response_model=PlatformLoginResponse)
def save_platform_login_state():
    data = get_browser_worker().save_state()
    return PlatformLoginResponse(success=True, data=PlatformLoginStateData(**data))


@router.post("/platforms/search", response_model=PlatformSearchResponse)
def search_platform_jobs_endpoint(
    req: PlatformSearchRequest,
    db: Session = Depends(get_db),
):
    data = search_platform_jobs(model_to_dict(req), db=db)
    return PlatformSearchResponse(success=True, data=PlatformSearchData(**data))


@router.post("/platforms/collect-current", response_model=PlatformSearchResponse)
def collect_current_platform_pages_endpoint(
    req: PlatformSearchRequest,
    db: Session = Depends(get_db),
):
    payload = model_to_dict(req)
    # Reuse resume text/parsed loading from search_platform_jobs before sending to worker.
    if db is not None and payload.get("resume_id"):
        try:
            from app.models.resume import Resume
            resume = db.get(Resume, int(payload["resume_id"]))
        except AttributeError:
            from app.models.resume import Resume
            resume = db.query(Resume).filter(Resume.id == int(payload["resume_id"])).first()
        if resume is not None:
            payload["resume_text"] = resume.raw_text or ""
            if resume.parsed_json:
                import json
                try:
                    payload["resume_parsed"] = json.loads(resume.parsed_json)
                except Exception:
                    payload["resume_parsed"] = {}
    data = get_browser_worker().collect_current_pages(payload)
    return PlatformSearchResponse(success=True, data=PlatformSearchData(**data))


@router.post("/platforms/clear-cache")
def clear_platform_cache_endpoint(db: Session = Depends(get_db)):
    from app.models.cached_job_search import CachedJobSearch
    count = db.query(CachedJobSearch).count()
    db.query(CachedJobSearch).delete()
    db.commit()
    return {"success": True, "message": f"已清空 {count} 条缓存记录"}


@router.post("/platforms/close-browser", response_model=PlatformLoginResponse)
def close_platform_browser_endpoint():
    data = get_browser_worker().close()
    return PlatformLoginResponse(success=True, data=PlatformLoginStateData(**data))
