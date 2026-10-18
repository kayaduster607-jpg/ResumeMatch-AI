from typing import Optional

from sqlalchemy import Text, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class JobDescription(BaseModel):
    __tablename__ = "job_descriptions"

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Stores JSON string: {"responsibilities","required_skills","nice_to_have","hard_requirements"}
    parsed_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<JobDescription id={self.id} title={self.title!r}>"
