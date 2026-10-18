from pydantic import BaseModel


class MockInterviewRequest(BaseModel):
    question: str
    answer: str
    question_type: str = "technical"  # technical / project / gap_based / scenario / behavioral
    jd_context: str = ""
    resume_context: str = ""


class DimensionScore(BaseModel):
    dimension: str
    score: float
    comment: str


class MockInterviewResult(BaseModel):
    score: float
    level: str            # excellent / good / fair / needs_improvement
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
    improved_answer: str = ""
    dimension_scores: list[DimensionScore] = []


class MockInterviewResponse(BaseModel):
    success: bool = True
    data: MockInterviewResult
