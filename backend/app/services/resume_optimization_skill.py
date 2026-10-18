"""Reusable resume rewrite rules.

This module translates the human resume-review process into deterministic
helpers that the FullRewriteAgent can use before/after LLM generation.

Design goals:
- Keep resume rewriting evidence-based, not JD-driven fabrication.
- Present projects in a concise resume format: 项目简介 / 技术栈 / 技术亮点.
- Avoid treating URLs, repo names and tiny implementation dependencies as a
  "technology stack".
- Use real metrics only; ask for a placeholder when a metric is missing.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


_NOISY_TECH_KEYWORDS = {
    "github", "repo", "repository", "仓库", "项目地址", "链接", "url", "http", "https",
    "readme", "license", "package-lock", "node_modules", "localstorage", "sessionstorage",
}

# These are not universally invalid technologies, but listing too many of them
# in a resume makes the stack look like dependency dumping. They can still be
# mentioned in bullets when they are central to the implementation.
_MINOR_DEPENDENCIES = {
    "pdf-parse", "sheetjs", "xlsx", "bcryptjs", "recharts", "tailwind css", "tailwind",
    "vite", "react", "vue", "next.js", "nextjs", "reportlab", "python-docx", "pymupdf",
    "pydantic", "sqlalchemy", "jieba", "localstorage",
}

_CORE_TECH_HINTS = {
    "python", "fastapi", "mysql", "postgresql", "redis", "docker", "linux", "kubernetes", "k8s",
    "langgraph", "langchain", "rag", "milvus", "chromadb", "elasticsearch", "bm25",
    "openai", "openai 兼容接口", "llm", "agent", "sse", "playwright", "asyncio", "restful api",
    "typescript", "node.js", "node", "java", "go", "spring", "vue", "react", "next.js",
}

_ACTION_VERBS = [
    "设计", "实现", "封装", "拆分", "构建", "优化", "接入", "整理", "沉淀", "修复", "支持", "完成",
]

_INFLATED_ROLE_WORDS = ["主导", "牵头", "负责人", "架构师", "从0到1", "全权负责", "独立负责架构"]


def split_items(value: Any) -> list[str]:
    """Convert arbitrary skill/tech values to a normalized string list."""
    if value is None:
        return []
    if isinstance(value, str):
        raw = re.split(r"[,，、/|;；\n]+", value)
        return [x.strip() for x in raw if x and x.strip()]
    if isinstance(value, dict):
        candidates = [value.get("name"), value.get("raw"), value.get("title"), value.get("field")]
        return [str(x).strip() for x in candidates if x]
    if isinstance(value, Iterable):
        items: list[str] = []
        for x in value:
            items.extend(split_items(x))
        return items
    return [str(value).strip()] if str(value).strip() else []




def parse_json_object_robust(raw: str) -> dict[str, Any] | None:
    """Parse an LLM JSON object with common repairs.

    Handles fenced code blocks, surrounding prose and trailing commas.
    Returns None instead of raising so callers can fall back to rule-based mode.
    """
    import json

    if not raw or not raw.strip():
        return None

    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    candidates: list[str] = [text]
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace and brace.group(0) not in candidates:
        candidates.append(brace.group(0))

    for candidate in candidates:
        repaired = candidate.strip().lstrip("﻿")
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
        try:
            parsed = json.loads(repaired)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            continue
    return None

def clean_tech_stack(raw_items: Any, matched_skills: list[str] | None = None, max_items: int = 8) -> list[str]:
    """Clean project technology stack for resume display.

    Rules:
    1. Remove URLs, GitHub/repo words, empty items and overly long fragments.
    2. Avoid dependency dumping; keep core languages/frameworks/databases/AI infra.
    3. Prioritize technologies that match the target JD.
    """
    matched_lower = {str(x).strip().lower() for x in (matched_skills or []) if str(x).strip()}
    cleaned: list[str] = []
    minor: list[str] = []
    for item in split_items(raw_items):
        text = re.sub(r"\s+", " ", item).strip(" -—:：；;,.，。")
        if not text or len(text) > 40:
            continue
        lower = text.lower()
        if any(k in lower for k in _NOISY_TECH_KEYWORDS):
            continue
        if lower in {x.lower() for x in cleaned}:
            continue
        is_core = lower in _CORE_TECH_HINTS or any(k in lower for k in matched_lower if k)
        if lower in _MINOR_DEPENDENCIES and not is_core:
            minor.append(text)
            continue
        cleaned.append(text)

    # If everything was filtered, keep a few minor items rather than return empty.
    if not cleaned:
        cleaned = minor[:max_items]

    def rank(x: str) -> tuple[int, str]:
        lx = x.lower()
        if lx in matched_lower or any(m in lx for m in matched_lower if m):
            return (0, lx)
        if lx in _CORE_TECH_HINTS:
            return (1, lx)
        return (2, lx)

    return sorted(cleaned, key=rank)[:max_items]


def extract_real_metrics(text: str) -> list[str]:
    """Extract numeric facts that already exist in source text."""
    if not text:
        return []
    patterns = [
        r"\d+(?:\.\d+)?\s?%",
        r"\d+(?:\.\d+)?\s?(?:ms|s|秒|分钟|小时|天|月|年)",
        r"\d+\s?(?:个|类|条|份|次|轮|页|篇|题|平台|城市|用户|接口|模块|表|字段|Prompt|Agent|服务)",
        r"Top-?\d+",
        r"Recall@\d+",
        r"mAP|Precision|Recall",
    ]
    found: list[str] = []
    for p in patterns:
        for m in re.finditer(p, text, flags=re.IGNORECASE):
            val = m.group(0).strip()
            if val not in found:
                found.append(val)
    return found[:8]


def contains_numeric_claim(text: str) -> bool:
    return bool(re.search(r"\d|%|倍|提升|降低|压缩|准确率|召回率|吞吐|延迟", text or ""))


def contains_inflated_role(text: str) -> bool:
    return any(w in (text or "") for w in _INFLATED_ROLE_WORDS)


def is_resume_style_line(line: str) -> bool:
    """Filter out advice/report style language from generated resume text."""
    bad_markers = ["建议你", "可以考虑", "原简历未提供", "需要补充", "分析如下", "优化建议"]
    return not any(x in line for x in bad_markers)


def build_project_intro(project: dict[str, Any]) -> str:
    name = str(project.get("name", "项目")).strip() or "项目"
    desc = str(project.get("description", "")).strip()
    role = str(project.get("role", "")).strip()
    if desc:
        # Keep the first sentence/line; avoid turning resume into project report.
        first = re.split(r"[。\n]", desc)[0].strip()
        intro = first[:120]
    else:
        intro = f"围绕{name}完成核心功能开发与工程化实现"
    if role and role not in intro:
        intro = f"{intro}；个人职责：{role}"
    return intro


def build_project_highlights(project: dict[str, Any], matched_skills: list[str] | None = None) -> list[str]:
    """Build concise project highlights from existing project facts."""
    desc = str(project.get("description", "")).strip()
    achievements = project.get("achievements", []) or []
    tech = clean_tech_stack(project.get("tech_stack", []), matched_skills=matched_skills)
    source_lines: list[str] = []
    source_lines.extend(split_items(achievements))
    if desc:
        # Break long descriptions into sentence fragments.
        source_lines.extend([x.strip() for x in re.split(r"[。；;\n]", desc) if x.strip()])

    highlights: list[str] = []
    for raw in source_lines:
        line = raw.strip(" -•·")
        if not line or not is_resume_style_line(line):
            continue
        if not any(v in line for v in _ACTION_VERBS):
            # Add a modest action verb without exaggerating role.
            line = "实现" + line if len(line) < 60 else "参与" + line
        if contains_numeric_claim(line):
            # Keep only because it came from source text.
            pass
        highlights.append(line[:150])
        if len(highlights) >= 3:
            break

    if not highlights:
        if tech:
            highlights.append(f"围绕 {'、'.join(tech[:4])} 完成核心模块实现，保证功能可运行与可维护")
        else:
            highlights.append("完成核心功能开发与联调，保留原始项目事实，未补写未经验证的指标")

    # Add metric placeholder only when source lacks real metric, and only once.
    source_text = desc + "\n" + "\n".join(split_items(achievements))
    if not extract_real_metrics(source_text) and len(highlights) < 4:
        highlights.append("[请补充：真实量化指标，如数据量、响应耗时、准确率、用户数或接口数量]")

    return [h for h in highlights if h][:4]


def project_to_resume_block(project: dict[str, Any], matched_skills: list[str] | None = None) -> str:
    """Format one project as 项目简介 / 技术栈 / 技术亮点."""
    name = str(project.get("name", "项目")).strip() or "项目"
    role = str(project.get("role", "")).strip()
    title = f"【{name}】" + (f" {role}" if role else "")
    tech = clean_tech_stack(project.get("tech_stack", []), matched_skills=matched_skills)
    tech_line = "、".join(tech) if tech else "[请补充：项目核心技术栈，不写 GitHub/Repo/过细依赖]"
    intro = build_project_intro(project)
    highlights = build_project_highlights(project, matched_skills=matched_skills)
    lines = [title, f"项目简介：{intro}", f"技术栈：{tech_line}", "技术亮点："]
    lines.extend([f"- {x}" for x in highlights])
    return "\n".join(lines)


def build_rewrite_guidelines() -> str:
    """A compact general resume-rewrite skill injected into the LLM prompt."""
    return """
【通用简历优化 Skill】
1. 先根据目标 JD 建模：岗位需要哪些硬技能、项目证据、业务场景、硬性条件；JD 需求只能作为优化方向，不能当作候选人经历证据。
2. 项目经历统一使用：项目简介 / 技术栈 / 技术亮点。技术亮点每条写"动作 + 技术实现 + 结果/约束"，避免写成长篇项目叙事。
3. 技术栈只写核心语言、框架、数据库、AI/Agent/RAG、云和工程能力；不要把 GitHub、Repo、URL、package-lock、localStorage、过细依赖和无关库当技术栈。
4. 量化数据必须来自原简历或项目文档；禁止编造准确率、提升百分比、代码行数、用户数等。没有真实数字时用 [请补充：真实指标]，或只写工程动作。
5. 候选人若是实习/校招定位，动词以"参与、实现、设计、优化、修复、整理、接入"为主；不要无依据写"主导、架构师、负责人、从0到1"。
6. 简历不是分析报告。禁止输出"建议你、原简历未提供、可以考虑、分析如下"等建议式语言，除非在 [请补充] 占位符中。
7. 每条关键描述必须绑定 resume_evidence 和 jd_evidence。risk 只由 resume_evidence 决定；只有 JD evidence 的描述必须 high risk + need_manual_confirm=true。
""".strip()
