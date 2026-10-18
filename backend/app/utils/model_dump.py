"""Pydantic v1/v2 compatible model serialization."""

from typing import Any


def model_to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, list):
        return [model_to_dict(x) for x in obj]
    if isinstance(obj, tuple):
        return [model_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: model_to_dict(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj
