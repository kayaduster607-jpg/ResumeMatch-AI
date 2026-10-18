"""Quality gates and reusable resume-polishing rules for full resume rewrite.

This module turns the general resume-optimization workflow into deterministic
post-processing logic. It does not replace LLM rewriting; it makes the output
closer to a real resume by enforcing:
- evidence-first writing;
- clean technology stack lines;
- intern-appropriate tone;
- no unverified metrics;
- project format: 项目简介 → 技术栈 → 技术亮点.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.schemas.rewrite_resume import (
    RewrittenResumeData,
    ResumeSection,
    RewriteQualityGateItem,
    RewriteStrategy,
    BulletEvidence,
)


TECH_STACK_PREFIXES = ("技术栈", "架构与技术", "技术选型", "核心技术")

# Tiny dependencies are useful in README, but they make resumes look like dependency lists.
# Map them to capability-level terms that interviewers care about.
DEPENDENCY_TO_CAPABILITY = {
    "PyMuPDF": "PDF 文本解析",
    "pdf-parse": "PDF 解析",
    "SheetJS": "Excel / CSV 解析",
    "bcryptjs": "密码加密 / Cookie Session",
    "ReportLab": "PDF 报告导出",
    "python-docx": "Word 报告导出",
    "Recharts": "数据可视化",
}

OVERCLAIM_TERMS = ("精通", "专家", "架构师", "主导", "负责整体架构", "独立负责全链路")
SUGGESTION_TERMS = ("建议你", "可以考虑", "原简历未提供", "需要补充", "从而提升竞争力")
METRIC_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:\d+(?:\.\d+)?\s*(?:%|秒|ms|s|分钟|小时|天|人|个|条|次|倍|万|k|K|页|轮|类|张|份|行|层|模块)|[一二三四五六七八九十]+\s*(?:个|条|类|张|份|轮|层|模块))"
)


def post_process_rewritten_resume(
    data: RewrittenResumeData,
    *,
    resume_text: str,
    resume_parsed: dict,
    jd_parsed: dict,
    matched_skills: list[str],
    missing_skills: list[str],
    problems: list[dict],
) -> RewrittenResumeData:
    """Apply the resume-improvement skill to LLM/rule-based rewrite output."""
    data.sections = [
        ResumeSection(title=s.title, content=clean_section_content(s.title, s.content))
        for s in (data.sections or [])
    ]
    data.full_text = clean_full_text(data.full_text)

    if data.summary:
        data.summary = _soften_intern_tone(data.summary)

    data.rewrite_strategy = data.rewrite_strategy or build_rewrite_strategy(
        resume_parsed=resume_parsed,
        jd_parsed=jd_parsed,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        problems=problems,
    )

    data.evidence_chain = reassess_evidence_chain(data.evidence_chain or [], resume_text)
    data.quality_gate = run_quality_gate(data, resume_text=resume_text)
    return data


def build_rewrite_strategy(
    *,
    resume_parsed: dict,
    jd_parsed: dict,
    matched_skills: list[str],
    missing_skills: list[str],
    problems: list[dict],
) -> RewriteStrategy:
    """Build a deterministic rewrite strategy summary for transparency."""
    jd_title = str(jd_parsed.get("title") or jd_parsed.get("job_title") or "目标岗位")
    required = _as_str_list(jd_parsed.get("required_skills", []))[:8]
    preferred = _as_str_list(jd_parsed.get("preferred_skills", []))[:5]
    responsibilities = _as_str_list(jd_parsed.get("responsibilities", []))[:5]

    projects = resume_parsed.get("projects", []) or []
    project_names = []
    for p in projects:
        if isinstance(p, dict):
            name = p.get("name") or p.get("project_name")
            if name:
                project_names.append(str(name))
        elif isinstance(p, str) and len(p) < 40:
            project_names.append(p)

    issue_titles = []
    for p in problems or []:
        if isinstance(p, dict):
            issue_titles.append(str(p.get("title") or p.get("type") or ""))
        else:
            issue_titles.append(str(p))
    issue_titles = [x for x in issue_titles if x][:6]

    return RewriteStrategy(
        target_role=jd_title,
        role_requirements=[*required, *preferred, *responsibilities][:12],
        evidence_summary=[
            f"命中技能：{', '.join(matched_skills[:8])}" if matched_skills else "命中技能：待根据简历事实确认",
            f"可优先使用项目：{', '.join(project_names[:5])}" if project_names else "可优先使用项目：原简历暂未结构化识别",
            f"待补足能力：{', '.join(missing_skills[:6])}" if missing_skills else "待补足能力：无明显缺失或待人工复核",
        ],
        section_order=["个人信息", "求职意向", "专业技能", "项目经历", "实习/工作经历", "教育背景", "证书/荣誉"],
        project_style="项目简介 → 技术栈 → 技术亮点；每个项目控制 3-5 条亮点，优先写架构、实现、评测、问题修复。",
        tech_stack_rules=[
            "技术栈写能力域和核心框架，不写 GitHub、Repo、安装包或过细依赖。",
            "前端库、解析库、加密库等仅在目标岗位相关时保留，否则转写成能力描述。",
        ],
        quantification_rules=[
            "只使用原简历、项目文档或评测结果中存在的数字。",
            "无真实指标时使用 [请补充：真实指标]，不要编造提升百分比或用户规模。",
        ],
        tone_rules=[
            "实习生定位使用：参与、设计、实现、优化、维护、修复。",
            "避免无证据使用：精通、专家、主导、架构师、全链路负责人。",
        ],
        omitted_or_compressed=issue_titles,
    )


def clean_section_content(title: str, content: str) -> str:
    """Clean a section according to resume writing rules."""
    lines = []
    for raw in (content or "").splitlines():
        line = raw.rstrip()
        if not line:
            lines.append(line)
            continue
        if _is_tech_stack_line(line):
            line = clean_tech_stack_line(line)
        line = _soften_intern_tone(line)
        lines.append(line)
    return "\n".join(lines).strip()


def clean_full_text(text: str) -> str:
    """Clean full resume text while preserving personal GitHub/contact lines."""
    cleaned_lines = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if _is_tech_stack_line(line):
            line = clean_tech_stack_line(line)
        else:
            line = _soften_intern_tone(line)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def clean_tech_stack_line(line: str) -> str:
    """Remove repo/link noise and convert tiny dependencies to capability terms."""
    if not line:
        return line

    prefix, sep, rest = _split_label(line)
    if not sep:
        prefix, sep, rest = "技术栈", "：", line

    # Remove repository/link fragments from tech-stack line only.
    rest = re.sub(r"(?:Repo|仓库|项目地址|GitHub|github)\s*[:：]\s*\S+", "", rest, flags=re.IGNORECASE)
    rest = re.sub(r"https?://\S+", "", rest)

    for dep, capability in DEPENDENCY_TO_CAPABILITY.items():
        rest = re.sub(re.escape(dep), capability, rest, flags=re.IGNORECASE)

    # Split by common delimiters and deduplicate.
    parts = [p.strip(" ，,、；;。.") for p in re.split(r"[、,，;；]", rest) if p.strip(" ，,、；;。.")]
    seen = set()
    normalized = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(p)

    if not normalized:
        return f"{prefix}{sep}[请补充：与目标岗位相关的核心技术能力]"
    return f"{prefix}{sep}{'、'.join(normalized[:12])}"


def run_quality_gate(data: RewrittenResumeData, *, resume_text: str) -> list[RewriteQualityGateItem]:
    """Run deterministic quality checks on rewritten resume."""
    text = "\n".join([data.summary or "", data.full_text or ""] + [s.content for s in data.sections or []])
    gates: list[RewriteQualityGateItem] = []

    suggestion_hits = [t for t in SUGGESTION_TERMS if t in text]
    gates.append(RewriteQualityGateItem(
        name="直接投递格式",
        status="warning" if suggestion_hits else "passed",
        message="仍出现建议报告式表述：" + "、".join(suggestion_hits) if suggestion_hits else "未发现明显建议报告式表述。",
    ))

    tech_stack_noise = []
    for line in text.splitlines():
        if _is_tech_stack_line(line) and re.search(r"github|repo|https?://", line, flags=re.IGNORECASE):
            tech_stack_noise.append(line[:80])
    gates.append(RewriteQualityGateItem(
        name="技术栈清洗",
        status="warning" if tech_stack_noise else "passed",
        message="技术栈中仍包含仓库/链接信息。" if tech_stack_noise else "技术栈未包含 GitHub、Repo 或链接噪声。",
    ))

    overclaim_hits = [t for t in OVERCLAIM_TERMS if t in text and t not in (resume_text or "")]
    gates.append(RewriteQualityGateItem(
        name="实习生语气",
        status="warning" if overclaim_hits else "passed",
        message="可能存在无依据拔高词：" + "、".join(overclaim_hits) if overclaim_hits else "未发现明显超出实习生定位的夸大表述。",
    ))

    unverified_metrics = find_unverified_metrics(text, resume_text)
    gates.append(RewriteQualityGateItem(
        name="量化数据真实性",
        status="warning" if unverified_metrics else "passed",
        message="存在原简历未出现的数字/指标，需人工确认：" + "、".join(unverified_metrics[:8]) if unverified_metrics else "未发现明显新增未验证量化指标。",
    ))

    high_risk = [e for e in data.evidence_chain or [] if e.risk == "high" or e.fabrication_check != "passed"]
    gates.append(RewriteQualityGateItem(
        name="证据链覆盖",
        status="warning" if high_risk else "passed",
        message=f"有 {len(high_risk)} 条改写需要人工确认。" if high_risk else "证据链未发现高风险改写。",
    ))
    return gates


def reassess_evidence_chain(chain: list[BulletEvidence], resume_text: str) -> list[BulletEvidence]:
    """Mark bullets with unverified metrics or overclaims as high risk."""
    if not chain:
        return chain

    resume_text = resume_text or ""
    for item in chain:
        bullet = item.rewritten_bullet or ""
        has_unverified_metric = bool(find_unverified_metrics(bullet, resume_text))
        has_overclaim = any(t in bullet and t not in resume_text for t in OVERCLAIM_TERMS)
        if has_unverified_metric or has_overclaim:
            item.risk = "high"
            item.fabrication_check = "warning"
            item.need_manual_confirm = True
        elif not item.resume_evidence:
            item.risk = "high"
            item.fabrication_check = "warning"
            item.need_manual_confirm = True
    return chain


def find_unverified_metrics(text: str, resume_text: str) -> list[str]:
    """Return metrics/numbers that appear in rewritten text but not original resume."""
    resume_text = resume_text or ""
    metrics = []
    for m in METRIC_RE.finditer(text or ""):
        value = m.group(0).strip()
        # Small years and dates are often section dates; only flag if absent from source.
        if value and value not in resume_text and value not in metrics:
            metrics.append(value)
    return metrics


def _is_tech_stack_line(line: str) -> bool:
    normalized = (line or "").strip().lstrip("-•* ")
    return any(normalized.startswith(p) or normalized.startswith(f"{p}：") or normalized.startswith(f"{p}:") for p in TECH_STACK_PREFIXES)


def _split_label(line: str) -> tuple[str, str, str]:
    if "：" in line:
        a, b = line.split("：", 1)
        return a.strip(), "：", b.strip()
    if ":" in line:
        a, b = line.split(":", 1)
        return a.strip(), ":", b.strip()
    return "", "", line


def _soften_intern_tone(text: str) -> str:
    """Reduce overclaiming tone when no evidence-specific decision is available."""
    if not text:
        return text
    replacements = {
        "精通": "熟悉",
        "专家级": "具备实践经验的",
        "主导整体架构": "参与架构设计与模块拆分",
        "负责整体架构": "参与架构设计与核心模块实现",
        "独立负责全链路": "参与全流程设计与实现",
    }
    result = text
    for a, b in replacements.items():
        result = result.replace(a, b)
    return result


def _as_str_list(value: Iterable | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[、,，;；\n]", value) if x.strip()]
    result = []
    for item in value:
        if isinstance(item, dict):
            v = item.get("name") or item.get("title") or item.get("raw") or item.get("text")
            if v:
                result.append(str(v))
        else:
            result.append(str(item))
    return [x for x in result if x]
