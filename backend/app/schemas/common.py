from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ResponseBase(BaseModel, Generic[T]):
    """Unified API response wrapper."""
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class PageResponse(BaseModel, Generic[T]):
    """Paginated response."""
    code: int = 0
    message: str = "success"
    data: list[T] = []
    total: int = 0


class ErrorResponse(BaseModel):
    """Error response."""
    code: str
    message: str
