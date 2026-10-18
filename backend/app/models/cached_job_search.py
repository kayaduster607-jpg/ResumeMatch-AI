from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Text, Integer, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CachedJobSearch(Base):
    __tablename__ = "cached_job_searches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    platforms_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    pages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    job_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    experience: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    education: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    total_found: Mapped[int] = mapped_column(Integer, default=0)
    total_after_filter: Mapped[int] = mapped_column(Integer, default=0)
    jobs_json: Mapped[str] = mapped_column(Text, nullable=False)  # LONGTEXT on MySQL
    errors_json: Mapped[str] = mapped_column(Text, default="[]")
    elapsed_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
