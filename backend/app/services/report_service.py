"""Structured report generation service.

This module must be fast and side-effect free for the report page.  Earlier
versions called DeepSeek again while opening the report, which made the page
hang on "正在加载报告".  This version only reads the existing MatchReport and
builds a report view from stored data.
"""

import json
from typing import Optional, Any

from sqlalchemy.orm import Session

from app.models.analysis_task import AnalysisTask, TaskStatus
from app.models.match_report import MatchReport
from app.models.resume import Resume
from app.models.job_description import JobDescription
from app.schemas.report import (
    FullReport,
    ReportSummary,
    SkillAnalysis,
    RewriteSuggestion,
    NextStep,
)
from app.schemas.analysis import ScoreDetail
from app.schemas.diagnosis import DiagnosisIssue
from app.core.exceptions import AppException


def generate_full_report(task_id: int, db: Session) -> FullReport:
    """Generate a comprehensive report for a completed analysis task.

    Important: do not call LLM-heavy rewrite/interview services here.  The report
    page should load instantly from the data already saved by /analysis/run.
    """
    task = _db_get(db, AnalysisTask, task_id)
    if task is None:
        raise AppException(f"Task {task_id} not found", code="NOT_FOUND", status_code=404)
    if task.status != TaskStatus.completed:
        raise AppException(f"Task {task_id} is not completed", code="NOT_COMPLETED")

    report = db.query(MatchReport).filter(MatchReport.task_id == task_id).first()
    if report is None:
        raise AppException(f"Report for task {task_id} not found", code="NOT_FOUND", status_code=404)

    resume = _db_get(db, Resume, task.resume_id)
    jd = _db_get(db, JobDescription, task.jd_id)

    score_detail, ai_analysis = _load_score_detail(report)

    problems_raw = _json_loads(report.problems_json, [])
    problems = []
    for p in problems_raw if isinstance(problems_raw, list) else []:
        try:
            problems.append(DiagnosisIssue(**(p or {})))
        except Exception:
            continue

    matched_skills = _json_loads(report.matched_skills_json, [])
    missing_skills = _json_loads(report.missing_skills_json, [])
    if not isinstance(matched_skills, list):
        matched_skills = []
    if not isinstance(missing_skills, list):
        missing_skills = []

    total_score = float(report.total_score or 0)
    match_level = _determine_level(total_score)
    conclusion = _build_conclusion(total_score, match_level, matched_skills, missing_skills, problems, ai_analysis)

    summary = ReportSummary(
        total_score=round(total_score, 1),
        match_level=match_level,
        one_sentence_conclusion=conclusion,
    )

    recommended = _recommend_skills(missing_skills, jd)
    skill_analysis = SkillAnalysis(
        matched_skills=[str(x) for x in matched_skills],
        missing_skills=[str(x) for x in missing_skills],
        recommended_skills_to_learn=recommended,
    )

    # Build lightweight rewrite suggestions from stored suggestions/problems.
    rewrite_suggestions = _stored_rewrite_suggestions(report, problems)

    next_steps = _build_next_steps(problems, missing_skills, score_detail, ai_analysis)

    markdown = _generate_markdown(
        summary, score_detail, skill_analysis, problems,
        rewrite_suggestions, [], next_steps,
        resume_filename=getattr(resume, "filename", "") if resume else "",
        jd_title=getattr(jd, "title", "") if jd else "",
    )

    return FullReport(
        summary=summary,
        score_detail=score_detail,
        skill_analysis=skill_analysis,
        resume_problems=problems,
        rewrite_suggestions=rewrite_suggestions,
        interview_questions=[],
        next_steps=next_steps,
        markdown_export=markdown,
    )


def _db_get(db: Session, model: Any, pk: int):
    try:
        return db.get(model, pk)
    except AttributeError:
        return db.query(model).filter(model.id == pk).first()


def _json_loads(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _load_score_detail(report: MatchReport) -> tuple[ScoreDetail, dict[str, Any]]:
    raw = _json_loads(report.report_json, {})
    ai_analysis: dict[str, Any] = {}
    score_payload: dict[str, Any] = {}
    if isinstance(raw, dict):
        # New analysis_service stores {score_detail, ai_analysis}.  Old reports
        # stored ScoreDetail directly.  Support both.
        if isinstance(raw.get("score_detail"), dict):
            score_payload = raw.get("score_detail") or {}
        else:
            score_payload = raw
        if isinstance(raw.get("ai_analysis"), dict):
            ai_analysis = raw.get("ai_analysis") or {}
    try:
        score_detail = ScoreDetail(**score_payload)
    except Exception:
        score_detail = ScoreDetail()
    return score_detail, ai_analysis


def _determine_level(score: float) -> str:
    if score >= 85:
        return "强匹配"
    if score >= 75:
        return "推荐投递"
    if score >= 60:
        return "可投递，需优化"
    if score >= 50:
        return "低优先级"
    return "不建议优先"


def _build_conclusion(score: float, level: str, matched: list[str], missing: list[str], problems: list, ai_analysis: dict[str, Any]) -> str:
    ai_conclusion = str(ai_analysis.get("overall_conclusion") or "").strip()
    if ai_conclusion:
        return ai_conclusion
    parts = [f"综合匹配度 {round(score, 1)} 分（{level}）"]
    if matched:
        parts.append(f"命中 {len(matched)} 项技能")
    if missing:
        parts.append(f"仍缺少 {len(missing)} 项关键技能或关键词")
    if problems:
        high_count = sum(1 for p in problems if getattr(p, "severity", "") == "high")
        if high_count > 0:
            parts.append(f"有 {high_count} 个高优先级问题需解决")
    return "，".join(parts) + "。"


def _recommend_skills(missing: list[str], jd: Optional[JobDescription]) -> list[str]:
    if not missing:
        return []
    priority = []
    secondary = []
    for skill in missing:
        s = str(skill)
        lower = s.lower()
        if any(kw in lower for kw in ["python", "java", "react", "vue", "fastapi", "django", "spring", "llm", "agent", "rag"]):
            priority.append(s)
        else:
            secondary.append(s)
    return (priority + secondary)[:8]


def _stored_rewrite_suggestions(report: MatchReport, problems: list[DiagnosisIssue]) -> list[RewriteSuggestion]:
    suggestions_raw = _json_loads(report.suggestions_json, [])
    out: list[RewriteSuggestion] = []
    if isinstance(suggestions_raw, list):
        for i, item in enumerate(suggestions_raw[:4], 1):
            if not isinstance(item, dict):
                continue
            text = item.get("suggestion") or item.get("action") or ""
            if not text:
                continue
            out.append(RewriteSuggestion(
                project_name=item.get("category") or f"优化建议 {i}",
                original_text="",
                rewritten_text=str(text),
                missing_info_to_add=[],
            ))
    if not out:
        for i, p in enumerate(problems[:4], 1):
            out.append(RewriteSuggestion(
                project_name=getattr(p, "title", "简历优化") or f"优化建议 {i}",
                original_text=getattr(p, "evidence", "") or "",
                rewritten_text=getattr(p, "suggestion", "") or "",
                missing_info_to_add=[],
            ))
    return out


def _build_next_steps(problems: list[DiagnosisIssue], missing: list[str], score_detail: ScoreDetail, ai_analysis: dict[str, Any]) -> list[NextStep]:
    steps: list[NextStep] = []
    raw_actions = ai_analysis.get("action_plan") or []
    if isinstance(raw_actions, list):
        for item in raw_actions[:5]:
            if isinstance(item, dict):
                action = item.get("action") or item.get("task") or item.get("建议") or ""
                reason = item.get("reason") or item.get("why") or item.get("原因") or "AI建议"
            else:
                action = str(item)
                reason = "AI建议"
            if action:
                steps.append(NextStep(priority=len(steps) + 1, action=str(action), reason=str(reason)))
    if len(steps) >= 5:
        return steps[:5]

    for p in problems:
        if getattr(p, "severity", "") in ("high", "medium") and len(steps) < 5:
            steps.append(NextStep(
                priority=len(steps) + 1,
                action=getattr(p, "suggestion", "") or "优化简历描述",
                reason=f"[{getattr(p, 'severity', 'medium')}] {getattr(p, 'title', '')}",
            ))
    if missing and len(steps) < 5:
        steps.append(NextStep(
            priority=len(steps) + 1,
            action=f"补充或学习以下关键词：{', '.join(str(x) for x in missing[:3])}",
            reason="这些是目标岗位相关但简历中较弱的技能或关键词。",
        ))
    if score_detail.project_score < 60 and len(steps) < 5:
        steps.append(NextStep(
            priority=len(steps) + 1,
            action="优化项目经历，补充技术细节、指标、个人贡献和业务结果。",
            reason=f"项目相关性得分较低（{score_detail.project_score}）。",
        ))
    if not steps:
        steps.append(NextStep(priority=1, action="直接投递，并准备围绕项目经历进行技术追问。", reason="当前匹配度可投递。"))
    return steps[:5]


def _generate_markdown(summary, score_detail, skill_analysis, problems, rewrite_suggestions, interview_questions, next_steps, resume_filename: str = "", jd_title: str = "") -> str:
    lines = [
        "# AI 简历 JD 匹配分析报告",
        "",
        f"- 简历：{resume_filename or '未命名简历'}",
        f"- 岗位：{jd_title or '未命名岗位'}",
        f"- 总分：{summary.total_score}",
        f"- 匹配等级：{summary.match_level}",
        f"- 结论：{summary.one_sentence_conclusion}",
        "",
        "## 评分详情",
        "| 维度 | 分数 | 说明 |",
        "|---|---:|---|",
        f"| 技能匹配 | {score_detail.skill_score} | {score_detail.skill_reason} |",
        f"| 项目相关性 | {score_detail.project_score} | {score_detail.project_reason} |",
        f"| 语义相似度 | {score_detail.semantic_score} | {score_detail.semantic_reason} |",
        f"| 硬性要求 | {score_detail.requirement_score} | {score_detail.requirement_reason} |",
        "",
        "## 技能分析",
        f"- 命中技能：{', '.join(skill_analysis.matched_skills) or '无'}",
        f"- 缺失技能：{', '.join(skill_analysis.missing_skills) or '无'}",
        f"- 建议学习：{', '.join(skill_analysis.recommended_skills_to_learn) or '无'}",
        "",
    ]
    if problems:
        lines.append("## 简历问题")
        for i, p in enumerate(problems, 1):
            lines.append(f"{i}. [{getattr(p, 'severity', '')}] {getattr(p, 'title', '')}")
            lines.append(f"   - 证据：{getattr(p, 'evidence', '')}")
            lines.append(f"   - 建议：{getattr(p, 'suggestion', '')}")
        lines.append("")
    if next_steps:
        lines.append("## 下一步行动")
        for step in next_steps:
            lines.append(f"{step.priority}. {step.action} - {step.reason}")
    return "\n".join(lines)
