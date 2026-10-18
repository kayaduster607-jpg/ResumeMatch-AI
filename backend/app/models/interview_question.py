from typing import Optional

import enum
from sqlalchemy import Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class QuestionType(str, enum.Enum):
    technical = "technical"
    project = "project"
    behavioral = "behavioral"
    gap_based = "gap_based"


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class InterviewQuestion(BaseModel):
    __tablename__ = "interview_questions"

    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=False, index=True)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty), default=Difficulty.medium)
    reference_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    task = relationship("AnalysisTask", lazy="noload")

    def __repr__(self) -> str:
        return f"<InterviewQuestion id={self.id} type={self.question_type.value}>"
