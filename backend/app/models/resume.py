from typing import Optional

from sqlalchemy import Text, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel


class Resume(BaseModel):
    __tablename__ = "resumes"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Stores JSON string: {"name","email","phone","education","experience","projects","skills",...}
    parsed_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Resume id={self.id} filename={self.filename!r}>"
