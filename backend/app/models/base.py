from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class TimestampMixin:
    """Mixin that adds created_at / updated_at to any model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )


class BaseModel(Base, TimestampMixin):
    """Abstract base with auto-increment id + timestamps."""
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
