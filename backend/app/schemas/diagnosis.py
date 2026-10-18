from pydantic import BaseModel


class DiagnosisIssue(BaseModel):
    type: str               # 问题类型
    severity: str           # high / medium / low
    title: str              # 问题标题
    evidence: str           # 原文证据
    reason: str             # 为什么这是问题
    suggestion: str         # 怎么改
    rewrite_example: str    # 改写示例（不编造经历）
