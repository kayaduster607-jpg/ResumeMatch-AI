from pydantic import BaseModel


class NormalizedSkill(BaseModel):
    raw: str          # 原始写法
    name: str         # 标准名称
    category: str     # 归类
    confidence: float  # 置信度 0-1
