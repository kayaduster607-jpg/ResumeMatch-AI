"""AI interactive interview service using the selected resume/JD.

Python 3.9 compatible.  Uses DeepSeek/OpenAI-compatible LLM when configured;
when LLM_STRICT_MODE=true, any LLM failure is surfaced instead of silently
falling back to shallow rule output.
"""

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppException, LLMCallError
from app.models.analysis_task import AnalysisTask, TaskStatus
from app.models.job_description import JobDescription
from app.models.rewritten_resume import RewrittenResume
from app.models.resume import Resume
from app.services.llm_client import get_llm_client, is_real_llm_enabled, extract_json_value


def start_interview(task_id: int, use_rewritten_resume: bool, db: Session) -> dict[str, Any]:
    ctx = _load_context(task_id, use_rewritten_resume, db)
    ai = _try_start_with_ai(ctx)
    if ai:
        return ai
    return _rule_start(ctx)


def interview_chat(task_id: int, message: str, history: list[dict[str, str]], use_rewritten_resume: bool, db: Session) -> dict[str, Any]:
    ctx = _load_context(task_id, use_rewritten_resume, db)
    msg = (message or "").strip()
    if not msg:
        raise AppException("请先输入你的回答。", code="EMPTY_MESSAGE")
    ai = _try_chat_with_ai(ctx, msg, history)
    if ai:
        return ai
    return _rule_chat(ctx, msg, history)


def finish_interview(task_id: int, history: list[dict[str, str]], use_rewritten_resume: bool, db: Session) -> dict[str, Any]:
    """Generate a comprehensive summary of the entire mock interview."""
    ctx = _load_context(task_id, use_rewritten_resume, db)
    ai = _try_finish_with_ai(ctx, history)
    if ai:
        return ai
    return _rule_finish(history)


def _load_context(task_id: int, use_rewritten_resume: bool, db: Session) -> dict[str, Any]:
    task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
    if task is None:
        raise AppException(f"分析记录 {task_id} 不存在。", code="NOT_FOUND", status_code=404)
    if task.status != TaskStatus.completed:
        raise AppException("请先完成分析匹配。", code="NOT_COMPLETED")
    resume = db.query(Resume).filter(Resume.id == task.resume_id).first()
    jd = db.query(JobDescription).filter(JobDescription.id == task.jd_id).first()
    if not resume or not jd:
        raise AppException("简历或岗位不存在。", code="DATA_MISSING")

    resume_text = resume.raw_text or ""
    rewritten_used = False
    if use_rewritten_resume:
        rewritten = db.query(RewrittenResume).filter(RewrittenResume.task_id == task_id).first()
        if rewritten and (rewritten.edited_text or rewritten.rewritten_text):
            resume_text = rewritten.edited_text or rewritten.rewritten_text or resume_text
            rewritten_used = True

    return {
        "task_id": task_id,
        "resume_text": resume_text,
        "jd_text": jd.raw_text or "",
        "resume_parsed": _safe_json(resume.parsed_json),
        "jd_parsed": _safe_json(jd.parsed_json),
        "jd_title": jd.title or _safe_json(jd.parsed_json).get("job_title", "目标岗位"),
        "company": jd.company or _safe_json(jd.parsed_json).get("company", ""),
        "rewritten_used": rewritten_used,
    }


def _safe_json(text: Optional[str]) -> dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def _try_start_with_ai(ctx: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not is_real_llm_enabled():
        return None
    system = "你是一位严格但友好的中文技术面试官。请基于候选人的简历和目标JD生成模拟面试开场。只返回JSON。"
    user = f"""
目标岗位：{ctx['jd_title']}
目标公司：{ctx['company']}
是否使用改写简历：{ctx['rewritten_used']}

JD：
{ctx['jd_text'][:2500]}

简历：
{ctx['resume_text'][:3500]}

请返回JSON：
{{
  "tips": ["面试注意事项1", "注意事项2"],
  "focus_points": ["重点考察点1", "重点考察点2"],
  "first_question": "第一道面试问题，要求候选人结合简历回答"
}}
"""
    try:
        data = get_llm_client().chat_json(system, user, temperature=0.2)
        return {
            "task_id": ctx["task_id"],
            "jd_title": ctx["jd_title"],
            "company": ctx["company"],
            "use_rewritten_resume": ctx["rewritten_used"],
            "tips": _as_list(data.get("tips")),
            "first_question": str(data.get("first_question") or "请用1分钟介绍自己，并说明你为什么适合这个岗位。"),
            "focus_points": _as_list(data.get("focus_points")),
            "used_ai": True,
        }
    except Exception as exc:
        if get_settings().LLM_STRICT_MODE:
            raise AppException(f"DeepSeek 面试开场生成失败：{exc}", code="LLM_INTERVIEW_FAILED", status_code=500) from exc
        return None


def _try_chat_with_ai(ctx: dict[str, Any], message: str, history: list[dict[str, str]]) -> Optional[dict[str, Any]]:
    if not is_real_llm_enabled():
        return None
    system = """你是一位中文技术面试官。你正在根据候选人的简历和目标JD进行模拟面试。
要求：
1. 针对候选人刚刚的回答给出具体反馈，不要空泛。
2. 指出回答中的亮点、风险、可补充证据。
3. 给出下一道追问，追问必须贴合JD和简历。
4. 只返回JSON。"""
    conv = "\n".join([f"{h.get('role','user')}: {h.get('content','')}" for h in (history or [])[-8:]])
    user = f"""
目标岗位：{ctx['jd_title']}
目标公司：{ctx['company']}

JD摘要：
{ctx['jd_text'][:2200]}

简历摘要：
{ctx['resume_text'][:3200]}

最近对话：
{conv}

候选人本轮回答：
{message}

请返回JSON：
{{
  "assistant_message": "面试官完整回复：先反馈，再给下一题",
  "feedback": "本轮回答具体反馈",
  "next_question": "下一道追问",
  "tips": ["下一轮注意事项1", "注意事项2"],
  "score": 0-100
}}
"""
    try:
        data = get_llm_client().chat_json(system, user, temperature=0.25)
        return {
            "assistant_message": str(data.get("assistant_message") or "我已收到你的回答。请继续结合项目细节补充说明。"),
            "feedback": str(data.get("feedback") or ""),
            "next_question": str(data.get("next_question") or "请补充一个最能证明你能力的项目案例。"),
            "tips": _as_list(data.get("tips")),
            "score": float(data.get("score") or 0),
            "used_ai": True,
        }
    except Exception as exc:
        if get_settings().LLM_STRICT_MODE:
            raise AppException(f"DeepSeek 模拟面试调用失败：{exc}", code="LLM_INTERVIEW_FAILED", status_code=500) from exc
        return None


def _rule_start(ctx: dict[str, Any]) -> dict[str, Any]:
    tips = ["回答尽量使用 STAR：背景、任务、行动、结果。", "项目经历要说清楚你的个人贡献，不要只讲团队做了什么。", "遇到不会的问题，说明排查思路和学习计划，不要硬编。"]
    points = ["岗位关键词与项目经历的对应关系", "技术选型和工程落地能力", "项目结果是否有数据支撑"]
    return {
        "task_id": ctx["task_id"],
        "jd_title": ctx["jd_title"],
        "company": ctx["company"],
        "use_rewritten_resume": ctx["rewritten_used"],
        "tips": tips,
        "first_question": f"请用1分钟介绍自己，并重点说明你为什么适合{ctx['jd_title']}。",
        "focus_points": points,
        "used_ai": False,
    }


def _rule_chat(ctx: dict[str, Any], message: str, history: list[dict[str, str]]) -> dict[str, Any]:
    score = min(85, max(45, len(message) // 4))
    feedback = "你的回答已经覆盖了一部分经历，但还需要补充：具体项目背景、你个人负责的动作、使用的技术栈、最终结果或量化指标。"
    next_question = "请挑一个最贴近目标岗位的项目，说明技术架构、你的职责、遇到的最大问题以及如何解决。"
    return {
        "assistant_message": f"{feedback}\n\n下一题：{next_question}",
        "feedback": feedback,
        "next_question": next_question,
        "tips": ["补充量化指标", "强调个人贡献", "回答中主动对应JD关键词"],
        "score": score,
        "used_ai": False,
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _try_finish_with_ai(ctx: dict[str, Any], history: list[dict[str, str]]) -> Optional[dict[str, Any]]:
    if not is_real_llm_enabled():
        return None
    conv_text = "\n".join([f"{h.get('role','user')}: {h.get('content','')}" for h in (history or [])])
    user_rounds = sum(1 for h in history if h.get("role") == "user")
    system = """你是一位资深中文技术面试官。请对候选人的整场模拟面试进行全面总结。
分析候选人的表现，给出具体、可操作的改进建议。只返回JSON。"""
    user = f"""
目标岗位：{ctx['jd_title']}
目标公司：{ctx['company']}

完整面试对话：
{conv_text[:6000]}

候选人共回答了 {user_rounds} 轮问题。

请返回JSON：
{{
  "overall_score": 0-100的整数,
  "overall_feedback": "3-5句话的总体评价，指出候选人的核心优势和最大短板",
  "strengths": ["亮点1", "亮点2", "亮点3"],
  "weaknesses": ["短板1", "短板2", "短板3"],
  "suggestions": ["面试前重点准备1", "面试前重点准备2", "面试前重点准备3", "面试前重点准备4"],
  "total_rounds": {user_rounds}
}}
"""
    try:
        data = get_llm_client().chat_json(system, user, temperature=0.25)
        return {
            "overall_score": int(data.get("overall_score") or 0),
            "overall_feedback": str(data.get("overall_feedback") or ""),
            "strengths": _as_list(data.get("strengths")),
            "weaknesses": _as_list(data.get("weaknesses")),
            "suggestions": _as_list(data.get("suggestions")),
            "total_rounds": int(data.get("total_rounds") or user_rounds),
        }
    except Exception as exc:
        if get_settings().LLM_STRICT_MODE:
            raise AppException(f"DeepSeek 面试总结生成失败：{exc}", code="LLM_INTERVIEW_FAILED", status_code=500) from exc
        return None


def _rule_finish(history: list[dict[str, str]]) -> dict[str, Any]:
    user_msgs = [h.get("content", "") for h in history if h.get("role") == "user"]
    total_rounds = len(user_msgs)
    avg_len = sum(len(m) for m in user_msgs) / max(total_rounds, 1)
    score = min(85, max(40, int(avg_len / 3)))
    return {
        "overall_score": score,
        "overall_feedback": f"你完成了 {total_rounds} 轮面试问答。你的回答{'较为详细' if avg_len > 100 else '可以更充实'}，建议在正式面试前针对目标岗位多做几次模拟练习。",
        "strengths": ["能够结合项目经历回答问题" if any("项目" in m for m in user_msgs) else "尝试将理论与经验结合", "回答态度积极" if total_rounds >= 2 else "开始建立面试节奏"],
        "weaknesses": [f"回答平均长度 {int(avg_len)} 字，建议更充实" if avg_len < 200 else "部分回答可以更精炼", "可以更多引用具体数据" if not any("%" in m or "提升" in m for m in user_msgs) else "部分表述可以更结构化"],
        "suggestions": [
            "每个回答使用 STAR 法则：背景-任务-行动-结果",
            "准备 3-5 个最能代表你能力的项目案例",
            "提前研究目标公司的产品和技术栈",
            "练习在 2-3 分钟内完成一个完整回答",
        ],
        "total_rounds": total_rounds,
    }
