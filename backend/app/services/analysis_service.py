"""Analysis orchestration service.

Coordinates: task creation → scoring → diagnosis → DeepSeek/OpenAI-compatible analysis → persistence.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.analysis_task import AnalysisTask, TaskStatus
from app.models.job_description import JobDescription
from app.models.match_report import MatchReport
from app.models.resume import Resume
from app.schemas.analysis import AIAnalysis, AnalysisResultData, ScoreDetail, SuggestionItem
from app.schemas.diagnosis import DiagnosisIssue
from app.services.diagnosis_service import diagnose
from app.services.llm_client import get_llm_client, get_llm_status, is_real_llm_enabled
from app.services.scoring_service import compute_scores
from app.services.resume_parse_service import parse_resume
from app.services.jd_parse_service import parse_jd


def _dump_model(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj)


def run_analysis(resume_id: int, jd_id: int, db: Session) -> AnalysisResultData:
    """Run full analysis pipeline: load data → score → diagnose → AI analysis → persist."""

    resume = db.get(Resume, resume_id)
    if resume is None:
        raise AppException(f"Resume {resume_id} not found", code="NOT_FOUND", status_code=404)
    if not resume.parsed_json:
        # 自动解析，避免用户还要手动调用 /resumes/{id}/parse。
        parse_resume(resume_id, db)
        resume = db.get(Resume, resume_id)
        if not resume or not resume.parsed_json:
            raise AppException(
                f"Resume {resume_id} 自动解析失败，请重新上传简历或检查 DeepSeek 配置。",
                code="RESUME_AUTO_PARSE_FAILED",
                status_code=500,
            )

    jd = db.get(JobDescription, jd_id)
    if jd is None:
        raise AppException(f"JobDescription {jd_id} not found", code="NOT_FOUND", status_code=404)
    if not jd.parsed_json:
        # 自动解析，避免导入岗位后未解析导致分析失败。
        parse_jd(jd_id, db)
        jd = db.get(JobDescription, jd_id)
        if not jd or not jd.parsed_json:
            raise AppException(
                f"JobDescription {jd_id} 自动解析失败，请检查岗位文本或 DeepSeek 配置。",
                code="JD_AUTO_PARSE_FAILED",
                status_code=500,
            )

    resume_parsed = json.loads(resume.parsed_json)
    jd_parsed = json.loads(jd.parsed_json)

    task = AnalysisTask(resume_id=resume_id, jd_id=jd_id, status=TaskStatus.processing)
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        scoring_result = compute_scores(
            resume_parsed=resume_parsed,
            jd_parsed=jd_parsed,
            resume_raw_text=resume.raw_text or "",
            jd_raw_text=jd.raw_text or "",
        )

        diagnosis_issues = diagnose(
            resume_parsed=resume_parsed,
            jd_parsed=jd_parsed,
            matched_skills=scoring_result.matched_skills,
            missing_skills=scoring_result.missing_skills,
        )
        all_problems = list(diagnosis_issues)

        suggestions = [
            SuggestionItem(category=issue.type, suggestion=issue.suggestion)
            for issue in diagnosis_issues
        ]

        ai_analysis = _generate_ai_analysis(
            resume_text=resume.raw_text or "",
            jd_text=jd.raw_text or "",
            resume_parsed=resume_parsed,
            jd_parsed=jd_parsed,
            total_score=scoring_result.total_score,
            score_detail=_dump_model(scoring_result.score_detail),
            matched_skills=scoring_result.matched_skills,
            missing_skills=scoring_result.missing_skills,
            problems=[_dump_model(p) for p in all_problems],
        )

        report_payload = {
            "score_detail": _dump_model(scoring_result.score_detail),
            "ai_analysis": _dump_model(ai_analysis),
            "analysis_version": "v2.5-deepseek",
        }

        report = MatchReport(
            task_id=task.id,
            total_score=scoring_result.total_score,
            skill_score=scoring_result.score_detail.skill_score,
            project_score=scoring_result.score_detail.project_score,
            semantic_score=scoring_result.score_detail.semantic_score,
            requirement_score=scoring_result.score_detail.requirement_score,
            matched_skills_json=json.dumps(scoring_result.matched_skills, ensure_ascii=False),
            missing_skills_json=json.dumps(scoring_result.missing_skills, ensure_ascii=False),
            problems_json=json.dumps([_dump_model(p) for p in all_problems], ensure_ascii=False),
            suggestions_json=json.dumps([_dump_model(s) for s in suggestions], ensure_ascii=False),
            report_json=json.dumps(report_payload, ensure_ascii=False),
        )
        db.add(report)
        task.status = TaskStatus.completed
        db.commit()
        db.refresh(report)

        return AnalysisResultData(
            task_id=task.id,
            report_id=report.id,
            total_score=scoring_result.total_score,
            score_detail=scoring_result.score_detail,
            matched_skills=scoring_result.matched_skills,
            missing_skills=scoring_result.missing_skills,
            problems=all_problems,
            suggestions=suggestions,
            ai_analysis=ai_analysis,
        )

    except AppException:
        task.status = TaskStatus.failed
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        task.status = TaskStatus.failed
        db.commit()
        raise AppException(f"Analysis failed: {exc}", code="ANALYSIS_ERROR", status_code=500) from exc


def _generate_ai_analysis(
    resume_text: str,
    jd_text: str,
    resume_parsed: dict,
    jd_parsed: dict,
    total_score: float,
    score_detail: dict,
    matched_skills: list[str],
    missing_skills: list[str],
    problems: list[dict],
) -> AIAnalysis:
    status = get_llm_status()
    if not is_real_llm_enabled():
        return _fallback_ai_analysis(status, total_score, matched_skills, missing_skills, problems)

    system_prompt = """
你是一位资深招聘匹配顾问、技术面试官和简历优化专家。你必须基于给定简历和JD做深入分析。
要求：
1. 不要编造简历中不存在的经历、项目、数据。
2. 必须指出证据：每个优势/风险都要说明来自简历还是JD。
3. 必须给出可执行改写方向和面试准备方向。
4. 只返回合法 JSON，不要 Markdown，不要额外解释。
""".strip()

    payload = {
        "resume_text": resume_text[:7000],
        "jd_text": jd_text[:5000],
        "resume_parsed": resume_parsed,
        "jd_parsed": jd_parsed,
        "scoring": {
            "total_score": total_score,
            "score_detail": score_detail,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "rule_diagnosis": problems,
        },
    }
    schema = {
        "overall_conclusion": "一句话结论，明确适合/风险/是否建议投递",
        "match_positioning": "候选人在该岗位中的定位，例如强技术匹配但项目证据不足",
        "key_strengths": [
            {"title": "优势点", "evidence": "简历证据", "why_relevant": "为什么对应JD"}
        ],
        "core_gaps": [
            {"gap": "差距", "impact": "影响", "fix_strategy": "怎么补"}
        ],
        "resume_rewrite_strategy": ["简历改写动作，必须具体到模块/项目/技能"],
        "interview_risks": ["面试可能被追问的风险点"],
        "action_plan": [
            {"priority": 1, "action": "下一步动作", "reason": "原因", "expected_result": "预期效果"}
        ],
        "questions_to_prepare": ["需要提前准备的问题"],
    }
    user_prompt = "请按以下 JSON Schema 输出深度匹配分析：\n" + json.dumps(schema, ensure_ascii=False, indent=2)
    user_prompt += "\n\n输入数据：\n" + json.dumps(payload, ensure_ascii=False, indent=2)

    try:
        client = get_llm_client()
        data = client.chat_json(system_prompt, user_prompt, temperature=0.15)
        if not isinstance(data, dict):
            raise ValueError("AI 返回不是 JSON 对象")
        data = _normalize_ai_analysis_payload(data)
        data.setdefault("provider", status.get("provider", ""))
        data.setdefault("model", status.get("model", ""))
        data["used_ai"] = True
        data["raw"] = dict(data)
        return AIAnalysis(**data)
    except Exception as exc:  # noqa: BLE001
        if get_settings().LLM_STRICT_MODE:
            raise AppException(
                f"DeepSeek/LLM 分析调用失败：{exc}。请检查 backend/.env 的 LLM_PROVIDER、DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL、DEEPSEEK_MODEL。",
                code="LLM_ANALYSIS_FAILED",
                status_code=500,
            ) from exc
        return _fallback_ai_analysis(status, total_score, matched_skills, missing_skills, problems)


def _normalize_ai_analysis_payload(data: dict) -> dict:
    """Make LLM JSON tolerant: DeepSeek may return strings where UI expects objects."""
    def as_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def list_of_text(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            out = []
            for item in value:
                text = as_text(item).strip()
                if text:
                    out.append(text)
            return out
        text = as_text(value).strip()
        return [text] if text else []

    def list_of_dict(value: Any, default_key: str) -> list[dict]:
        if value is None:
            return []
        if isinstance(value, list):
            out = []
            for item in value:
                if isinstance(item, dict):
                    out.append(item)
                else:
                    text = as_text(item).strip()
                    if text:
                        out.append({default_key: text})
            return out
        if isinstance(value, dict):
            return [value]
        text = as_text(value).strip()
        return [{default_key: text}] if text else []

    normalized = dict(data)
    normalized["overall_conclusion"] = as_text(normalized.get("overall_conclusion"))
    normalized["match_positioning"] = as_text(normalized.get("match_positioning"))
    normalized["key_strengths"] = list_of_dict(normalized.get("key_strengths"), "title")
    normalized["core_gaps"] = list_of_dict(normalized.get("core_gaps"), "gap")
    normalized["action_plan"] = list_of_dict(normalized.get("action_plan"), "action")
    normalized["resume_rewrite_strategy"] = list_of_text(normalized.get("resume_rewrite_strategy"))
    normalized["interview_risks"] = list_of_text(normalized.get("interview_risks"))
    normalized["questions_to_prepare"] = list_of_text(normalized.get("questions_to_prepare"))
    return normalized


def _fallback_ai_analysis(status: dict, total_score: float, matched_skills: list[str], missing_skills: list[str], problems: list[dict]) -> AIAnalysis:
    return AIAnalysis(
        provider=status.get("provider", "mock"),
        model=status.get("model", "rule-based"),
        used_ai=False,
        overall_conclusion=f"规则分析分数 {total_score:.1f}。当前未启用真实AI或AI不可用。",
        match_positioning="仅基于规则评分，建议配置 DeepSeek 后重新分析。",
        key_strengths=[{"title": "已命中技能", "evidence": "、".join(matched_skills[:10]), "why_relevant": "技能与JD关键词存在重合"}],
        core_gaps=[{"gap": s, "impact": "JD要求但简历未明显体现", "fix_strategy": "在项目或技能区补充真实使用证据"} for s in missing_skills[:8]],
        resume_rewrite_strategy=["启用 DeepSeek 后生成更具体的项目级改写建议。"],
        interview_risks=[p.get("title", str(p)) for p in problems[:5]],
        action_plan=[{"priority": 1, "action": "配置 DeepSeek 并重新运行分析", "reason": "当前是规则兜底", "expected_result": "获得更深入的岗位定制分析"}],
        questions_to_prepare=[],
    )


def get_analysis_detail(task_id: int, db: Session) -> AnalysisResultData:
    task = db.get(AnalysisTask, task_id)
    if task is None:
        raise AppException(f"Task {task_id} not found", code="NOT_FOUND", status_code=404)
    if task.status != TaskStatus.completed:
        raise AppException(f"Task {task_id} is not completed (status: {task.status.value})", code="NOT_COMPLETED")

    report = db.query(MatchReport).filter(MatchReport.task_id == task_id).first()
    if report is None:
        raise AppException(f"Report for task {task_id} not found", code="NOT_FOUND", status_code=404)

    report_raw = json.loads(report.report_json) if report.report_json else {}
    if "score_detail" in report_raw:
        score_detail = ScoreDetail(**(report_raw.get("score_detail") or {}))
        ai_analysis = AIAnalysis(**(report_raw.get("ai_analysis") or {}))
    else:
        # Backward compatibility with old reports that stored only ScoreDetail.
        score_detail = ScoreDetail(**report_raw)
        ai_analysis = AIAnalysis()

    problems_raw = json.loads(report.problems_json) if report.problems_json else []
    problems = [DiagnosisIssue(**p) for p in problems_raw]

    suggestions_raw = json.loads(report.suggestions_json) if report.suggestions_json else []
    suggestions = [SuggestionItem(**s) for s in suggestions_raw]

    return AnalysisResultData(
        task_id=task.id,
        report_id=report.id,
        total_score=report.total_score,
        score_detail=score_detail,
        matched_skills=json.loads(report.matched_skills_json) if report.matched_skills_json else [],
        missing_skills=json.loads(report.missing_skills_json) if report.missing_skills_json else [],
        problems=problems,
        suggestions=suggestions,
        ai_analysis=ai_analysis,
    )


def list_analysis_history(db: Session) -> list[dict]:
    tasks = (
        db.query(AnalysisTask)
        .options(joinedload(AnalysisTask.resume), joinedload(AnalysisTask.jd))
        .order_by(AnalysisTask.created_at.desc())
        .all()
    )

    task_ids = [t.id for t in tasks]
    reports = db.query(MatchReport).filter(MatchReport.task_id.in_(task_ids)).all() if task_ids else []
    report_map = {r.task_id: r for r in reports}

    results = []
    for task in tasks:
        resume = task.resume
        jd = task.jd
        report = report_map.get(task.id)
        score = report.total_score if report else 0.0
        if score >= 85:
            level = "强匹配"
        elif score >= 75:
            level = "推荐投递"
        elif score >= 60:
            level = "可投递"
        elif score >= 50:
            level = "低优先级"
        else:
            level = "不建议投递"

        results.append({
            "task_id": task.id,
            "resume_id": resume.id if resume else 0,
            "jd_id": jd.id if jd else 0,
            "resume_filename": resume.filename if resume else "unknown",
            "jd_title": jd.title if jd else "unknown",
            "jd_company": jd.company if jd else "",
            "total_score": score,
            "match_level": level,
            "status": task.status.value,
            "created_at": task.created_at.isoformat() if task.created_at else "",
        })
    return results
