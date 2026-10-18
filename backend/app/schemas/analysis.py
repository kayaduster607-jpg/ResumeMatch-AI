from typing import Any

from pydantic import BaseModel, Field

from app.schemas.diagnosis import DiagnosisIssue


class AnalysisRequest(BaseModel):
    resume_id: int
    jd_id: int


class ScoreDetail(BaseModel):
    skill_score: float = 0.0
    skill_reason: str = ""
    project_score: float = 0.0
    project_reason: str = ""
    semantic_score: float = 0.0
    semantic_reason: str = ""
    requirement_score: float = 0.0
    requirement_reason: str = ""


class SuggestionItem(BaseModel):
    category: str
    suggestion: str


class AIAnalysis(BaseModel):
    provider: str = ""
    model: str = ""
    used_ai: bool = False
    overall_conclusion: str = ""
    match_positioning: str = ""
    key_strengths: list[dict[str, Any]] = Field(default_factory=list)
    core_gaps: list[dict[str, Any]] = Field(default_factory=list)
    resume_rewrite_strategy: list[str] = Field(default_factory=list)
    interview_risks: list[str] = Field(default_factory=list)
    action_plan: list[dict[str, Any]] = Field(default_factory=list)
    questions_to_prepare: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class AnalysisResultData(BaseModel):
    task_id: int
    report_id: int
    total_score: float
    score_detail: ScoreDetail
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    problems: list[DiagnosisIssue] = Field(default_factory=list)
    suggestions: list[SuggestionItem] = Field(default_factory=list)
    ai_analysis: AIAnalysis = Field(default_factory=AIAnalysis)


class AnalysisRunResponse(BaseModel):
    success: bool = True
    data: AnalysisResultData


class AnalysisHistoryItem(BaseModel):
    task_id: int
    resume_id: int = 0
    jd_id: int = 0
    resume_filename: str
    jd_title: str
    jd_company: str = ""
    total_score: float
    match_level: str = ""
    status: str
    created_at: str


class AnalysisHistoryResponse(BaseModel):
    success: bool = True
    data: list[AnalysisHistoryItem] = Field(default_factory=list)
    total: int = 0


class AnalysisDetailResponse(BaseModel):
    success: bool = True
    data: AnalysisResultData
