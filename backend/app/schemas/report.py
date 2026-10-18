from pydantic import BaseModel
from app.schemas.analysis import ScoreDetail
from app.schemas.diagnosis import DiagnosisIssue
from app.schemas.interview import InterviewQuestionItem


class ReportSummary(BaseModel):
    total_score: float
    match_level: str                # 非常匹配 / 较匹配 / 一般 / 较不匹配
    one_sentence_conclusion: str


class SkillAnalysis(BaseModel):
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    recommended_skills_to_learn: list[str] = []


class RewriteSuggestion(BaseModel):
    project_name: str
    original_text: str
    rewritten_text: str
    missing_info_to_add: list[str] = []


class NextStep(BaseModel):
    priority: int
    action: str
    reason: str


class FullReport(BaseModel):
    summary: ReportSummary
    score_detail: ScoreDetail
    skill_analysis: SkillAnalysis
    resume_problems: list[DiagnosisIssue] = []
    rewrite_suggestions: list[RewriteSuggestion] = []
    interview_questions: list[InterviewQuestionItem] = []
    next_steps: list[NextStep] = []
    markdown_export: str = ""


class ReportResponse(BaseModel):
    success: bool = True
    data: FullReport
