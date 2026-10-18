from typing import Optional
from sqlalchemy import Text, String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class RewrittenResume(BaseModel):
    __tablename__ = "rewritten_resumes"

    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_tasks.id"), nullable=False, index=True)
    resume_id: Mapped[int] = mapped_column(Integer, ForeignKey("resumes.id"), nullable=False)
    jd_id: Mapped[int] = mapped_column(Integer, ForeignKey("job_descriptions.id"), nullable=False)

    # The rewritten resume content
    rewritten_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured JSON: sections, highlights, changes summary
    rewritten_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # User-edited version (if user makes changes in the editor)
    edited_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Generation method: "llm" or "rule"
    source: Mapped[str] = mapped_column(String(20), default="rule", nullable=False)

    def __repr__(self) -> str:
        return f"<RewrittenResume id={self.id} task_id={self.task_id}>"
