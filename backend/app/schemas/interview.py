from pydantic import BaseModel


class InterviewQuestionItem(BaseModel):
    question_type: str      # technical / project / gap_based / scenario / behavioral
    difficulty: str         # easy / medium / hard
    question: str
    why_ask: str
    reference_answer: str
    related_resume_evidence: str = ""
    related_jd_requirement: str = ""


class InterviewQuestionsData(BaseModel):
    questions: list[InterviewQuestionItem] = []


class InterviewQuestionsResponse(BaseModel):
    success: bool = True
    data: InterviewQuestionsData
