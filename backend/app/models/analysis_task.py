from typing import Optional

import enum
from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class TaskStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnalysisTask(BaseModel):
    __tablename__ = "analysis_tasks"

    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False, index=True)
    jd_id: Mapped[int] = mapped_column(ForeignKey("job_descriptions.id"), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending, nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    # Relationships
    resume = relationship("Resume", lazy="noload")
    jd = relationship("JobDescription", lazy="noload")

    def __repr__(self) -> str:
        return f"<AnalysisTask id={self.id} status={self.status.value}>"
