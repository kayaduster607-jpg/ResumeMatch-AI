"""Resume project rewrite service.

Generates improved project descriptions based on diagnosis issues,
without fabricating experience or data.
"""

import json
import re

from sqlalchemy.orm import Session

from app.models.analysis_task import AnalysisTask, TaskStatus
from app.models.match_report import MatchReport
from app.models.resume import Resume
from app.models.job_description import JobDescription
from app.schemas.rewrite import ProjectRewrite, RewriteData
from app.services.diagnosis_service import diagnose
from app.services.scoring_service import compute_scores
from app.services.skill_normalizer import normalize_skills
from app.core.exceptions import AppException


def generate_rewrites(task_id: int, db: Session) -> RewriteData:
    """Generate rewrite suggestions for all projects in a resume."""
    task, resume_parsed, jd_parsed = _load_task_data(task_id, db)

    # Get diagnosis for context
    scoring = compute_scores(resume_parsed, jd_parsed, "", "")
    issues = diagnose(resume_parsed, jd_parsed, scoring.matched_skills, scoring.missing_skills)

    jd_skills = {s.name.lower(): s.name for s in normalize_skills(
        jd_parsed.get("required_skills", []) + jd_parsed.get("preferred_skills", [])
    )}

    rewrites: list[ProjectRewrite] = []
    for proj in resume_parsed.get("projects", []):
        rewrite = _rewrite_project(proj, issues, jd_skills, jd_parsed)
        rewrites.append(rewrite)

    return RewriteData(rewrites=rewrites)


def _load_task_data(task_id: int, db: Session):
    task = db.get(AnalysisTask, task_id)
    if task is None:
        raise AppException(f"Task {task_id} not found", code="NOT_FOUND", status_code=404)
    if task.status != TaskStatus.completed:
        raise AppException(f"Task {task_id} is not completed", code="NOT_COMPLETED")

    resume = db.get(Resume, task.resume_id)
    jd = db.get(JobDescription, task.jd_id)
    if not resume or not resume.parsed_json or not jd or not jd.parsed_json:
        raise AppException("Resume or JD data missing", code="DATA_MISSING")

    return task, json.loads(resume.parsed_json), json.loads(jd.parsed_json)


def _rewrite_project(
    proj: dict,
    issues: list,
    jd_skills: dict[str, str],
    jd_parsed: dict,
) -> ProjectRewrite:
    name = proj.get("name", "未命名项目")
    desc = proj.get("description", "")
    tech_stack = proj.get("tech_stack", [])
    achievements = proj.get("achievements", [])
    role = proj.get("role", "")

    original_text = desc
    if achievements:
        original_text += "\n" + "\n".join(achievements)

    # Collect problems for this project
    proj_problems: list[str] = []
    for issue in issues:
        if name in issue.evidence or name in issue.title:
            proj_problems.append(issue.title)

    # Identify missing info
    missing_info: list[str] = []

    # Check quantification
    has_metrics = bool(re.search(r"\d+\s*[%％]|\d+\s*[万kK]|\d+\s*(?:ms|QPS|TPS)", desc))
    if not has_metrics:
        missing_info.append("量化指标: 接口数量、数据量、响应时间、准确率、并发数等")

    # Check tech detail
    tech_norm = {s.lower() for s in tech_stack}
    jd_skill_overlap = tech_norm & jd_skills.keys()
    missing_jd_skills = set(jd_skills.keys()) - tech_norm
    if missing_jd_skills and len(missing_jd_skills) > len(jd_skill_overlap):
        missing_info.append(f"可补充与 JD 相关的技术栈: {', '.join(list(missing_jd_skills)[:3])}")

    # Check role clarity
    if not role or len(role) < 5:
        missing_info.append("明确你的角色: 核心开发 / 技术负责人 / 全栈开发等")

    # Check business context
    has_context = any(kw in desc for kw in ["场景", "业务", "用户", "需求", "背景", "目标"])
    if not has_context:
        missing_info.append("补充项目背景: 解决什么问题、服务什么业务场景")

    # Build rewritten text
    rewritten = _build_rewrite(proj, jd_skills, jd_parsed)

    return ProjectRewrite(
        project_name=name,
        original_text=original_text.strip(),
        problems=proj_problems,
        rewritten_text=rewritten,
        missing_info_to_add=missing_info,
    )


def _build_rewrite(proj: dict, jd_skills: dict[str, str], jd_parsed: dict) -> str:
    """Build an improved project description without fabricating data."""
    name = proj.get("name", "")
    desc = proj.get("description", "")
    tech_stack = proj.get("tech_stack", [])
    role = proj.get("role", "")
    achievements = proj.get("achievements", [])

    parts: list[str] = []

    # Part 1: Role + Project context
    if role and len(role) > 3:
        parts.append(f"【{role}】")
    else:
        parts.append("【项目开发】")

    # Part 2: Tech stack highlight
    if tech_stack:
        tech_str = "、".join(tech_stack[:6])
        parts.append(f"技术栈: {tech_str}")

    # Part 3: Improved description
    if desc:
        improved_desc = _improve_description(desc, tech_stack, jd_skills)
        parts.append(improved_desc)

    # Part 4: Achievements with placeholders for metrics
    if achievements:
        parts.append("核心成果:")
        for ach in achievements[:3]:
            parts.append(f"  - {ach}")
    elif not has_quantification(desc):
        parts.append("核心成果: [请补充量化指标，如: 接口数量、数据量、响应时间、准确率等]")

    return "\n".join(parts)


def _improve_description(desc: str, tech_stack: list[str], jd_skills: dict[str, str]) -> str:
    """Improve description by expanding vague phrases."""
    improved = desc

    # Replace vague starters with more specific ones
    vague_replacements = {
        "负责开发": "设计并实现",
        "参与开发": "参与设计与实现",
        "负责": "主导",
        "完成": "实现",
    }

    for vague, specific in vague_replacements.items():
        if improved.startswith(vague):
            improved = improved.replace(vague, specific, 1)
            break

    # If description is very short, suggest expansion
    if len(improved) < 30 and tech_stack:
        tech_str = "、".join(tech_stack[:3])
        improved = f"基于 {tech_str} {improved}"

    return improved


def has_quantification(text: str) -> bool:
    return bool(re.search(r"\d+\s*[%％]|\d+\s*[万kK]|\d+\s*(?:ms|QPS|TPS|个|条|次)", text))
