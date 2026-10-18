from fastapi import APIRouter
from app.api.v1.endpoints import resume, job_description, analysis, interview

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(resume.router, prefix="/resumes", tags=["Resume"])
api_router.include_router(job_description.router, prefix="/jds", tags=["Job Description"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(interview.router, prefix="/interview", tags=["Mock Interview"])
