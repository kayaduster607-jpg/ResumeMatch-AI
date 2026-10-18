from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.mock_interview import MockInterviewRequest, MockInterviewResponse
from app.services.interactive_interview_service import finish_interview, interview_chat, start_interview
from app.services.mock_interview_service import score_answer

router = APIRouter()


class InterviewStartRequest(BaseModel):
    task_id: int
    use_rewritten_resume: bool = True


class InterviewStartResponse(BaseModel):
    success: bool = True
    data: dict = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str
    content: str


class InterviewChatRequest(BaseModel):
    task_id: int
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    use_rewritten_resume: bool = True


class InterviewChatResponse(BaseModel):
    success: bool = True
    data: dict = Field(default_factory=dict)


class InterviewFinishRequest(BaseModel):
    task_id: int
    history: list[ChatMessage] = Field(default_factory=list)
    use_rewritten_resume: bool = True


class InterviewFinishResponse(BaseModel):
    success: bool = True
    data: dict = Field(default_factory=dict)


@router.post("/score", response_model=MockInterviewResponse)
def score_interview_answer(req: MockInterviewRequest):
    result = score_answer(req)
    return MockInterviewResponse(success=True, data=result)


@router.post("/start", response_model=InterviewStartResponse)
def start_interview_endpoint(req: InterviewStartRequest, db: Session = Depends(get_db)):
    data = start_interview(req.task_id, req.use_rewritten_resume, db)
    return InterviewStartResponse(success=True, data=data)


@router.post("/chat", response_model=InterviewChatResponse)
def interview_chat_endpoint(req: InterviewChatRequest, db: Session = Depends(get_db)):
    history = _convert_history(req.history)
    data = interview_chat(req.task_id, req.message, history, req.use_rewritten_resume, db)
    return InterviewChatResponse(success=True, data=data)


@router.post("/finish", response_model=InterviewFinishResponse)
def finish_interview_endpoint(req: InterviewFinishRequest, db: Session = Depends(get_db)):
    history = _convert_history(req.history)
    data = finish_interview(req.task_id, history, req.use_rewritten_resume, db)
    return InterviewFinishResponse(success=True, data=data)


def _convert_history(items: list[ChatMessage]) -> list[dict]:
    result = []
    for item in items:
        if hasattr(item, "model_dump"):
            result.append(item.model_dump())
        elif hasattr(item, "dict"):
            result.append(item.dict())
        else:
            result.append(dict(item))
    return result
