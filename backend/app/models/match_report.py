from typing import Optional

from sqlalchemy import Text, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class MatchReport(BaseModel):
    __tablename__ = "match_reports"

    task_id: Mapped[int] = mapped_column(ForeignKey("analysis_tasks.id"), nullable=False, unique=True, index=True)

    # ── Dimension Scores (0-100) ──────────────────────
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    skill_score: Mapped[float] = mapped_column(Float, default=0.0)
    project_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    requirement_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Detail JSON (stored as TEXT) ──────────────────
    matched_skills_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    missing_skills_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problems_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Full report snapshot
    report_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    task = relationship("AnalysisTask", lazy="noload")

    def __repr__(self) -> str:
        return f"<MatchReport id={self.id} task_id={self.task_id} total={self.total_score}>"
