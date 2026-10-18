"""Scoring engine for resume-JD matching.

Dimensions:
- skill_score (40%): required/preferred skill match
- project_score (25%): project relevance and quality
- semantic_score (20%): text similarity
- requirement_score (15%): hard requirements (education, experience)

Note: Problem diagnosis is handled by diagnosis_service, not here.
"""

import math
import re
from typing import Optional

from app.schemas.analysis import ScoreDetail
from app.services.skill_normalizer import normalize_skills
from app.services.embedding_service import get_embedding_service


# ── Weights ────────────────────────────────────────────

W_SKILL = 0.40
W_PROJECT = 0.25
W_SEMANTIC = 0.20
W_REQUIREMENT = 0.15


class ScoringResult:
    def __init__(
        self,
        total_score: float,
        score_detail: ScoreDetail,
        matched_skills: list[str],
        missing_skills: list[str],
    ):
        self.total_score = total_score
        self.score_detail = score_detail
        self.matched_skills = matched_skills
        self.missing_skills = missing_skills


def compute_scores(
    resume_parsed: dict,
    jd_parsed: dict,
    resume_raw_text: str,
    jd_raw_text: str,
) -> ScoringResult:
    """Run all scoring dimensions and return aggregated result."""

    # ── 1. Skill Score ─────────────────────────────────
    skill_score, skill_reason, matched, missing = _score_skills(
        resume_parsed, jd_parsed
    )

    # ── 2. Project Score ───────────────────────────────
    project_score, project_reason = _score_projects(
        resume_parsed, jd_parsed
    )

    # ── 3. Semantic Score ──────────────────────────────
    semantic_score, semantic_reason = _score_semantic(
        resume_raw_text, jd_raw_text
    )

    # ── 4. Requirement Score ───────────────────────────
    requirement_score, requirement_reason = _score_requirements(
        resume_parsed, jd_parsed
    )

    # ── Aggregate ──────────────────────────────────────
    total = (
        _safe_score(skill_score) * W_SKILL
        + _safe_score(project_score) * W_PROJECT
        + _safe_score(semantic_score) * W_SEMANTIC
        + _safe_score(requirement_score) * W_REQUIREMENT
    )

    score_detail = ScoreDetail(
        skill_score=_safe_score(skill_score),
        skill_reason=skill_reason,
        project_score=_safe_score(project_score),
        project_reason=project_reason,
        semantic_score=_safe_score(semantic_score),
        semantic_reason=semantic_reason,
        requirement_score=_safe_score(requirement_score),
        requirement_reason=requirement_reason,
    )

    return ScoringResult(
        total_score=_safe_score(total),
        score_detail=score_detail,
        matched_skills=matched,
        missing_skills=missing,
    )


# ── Skill Scoring ──────────────────────────────────────

def _score_skills(
    resume_parsed: dict, jd_parsed: dict
) -> tuple[float, str, list[str], list[str]]:
    """Score based on required and preferred skill overlap."""
    resume_skills_raw = resume_parsed.get("skills", [])
    # Also collect skills from projects and work experience
    for proj in resume_parsed.get("projects", []):
        resume_skills_raw.extend(proj.get("tech_stack", []))

    jd_required = jd_parsed.get("required_skills", [])
    jd_preferred = jd_parsed.get("preferred_skills", [])

    if not jd_required and not jd_preferred:
        return 70.0, "JD 未列出明确技能要求，给予中性分", [], []

    # Normalize all skills
    resume_norm = {s.name.lower() for s in normalize_skills(resume_skills_raw)}
    required_norm = {s.name.lower(): s.name for s in normalize_skills(jd_required)}
    preferred_norm = {s.name.lower(): s.name for s in normalize_skills(jd_preferred)}

    # Match required
    matched_req = required_norm.keys() & resume_norm
    missing_req = required_norm.keys() - resume_norm

    # Match preferred
    matched_pref = preferred_norm.keys() & resume_norm

    matched_names = [required_norm[k] for k in matched_req]
    matched_names += [preferred_norm[k] for k in matched_pref]
    missing_names = [required_norm[k] for k in missing_req]

    # Calculate score
    if required_norm:
        req_ratio = len(matched_req) / len(required_norm)
    else:
        req_ratio = 0.8  # no required skills listed

    pref_bonus = (len(matched_pref) / max(len(preferred_norm), 1)) * 10

    raw_score = req_ratio * 90 + pref_bonus
    score = min(100.0, raw_score)

    # Build detailed reason
    matched_req_names = [required_norm[k] for k in matched_req]
    missing_req_names = [required_norm[k] for k in missing_req]
    matched_pref_names = [preferred_norm[k] for k in matched_pref]

    reason_parts = []
    if required_norm:
        reason_parts.append(f"必备技能命中 {len(matched_req)}/{len(required_norm)}")
        if matched_req_names:
            reason_parts.append(f"已匹配: {', '.join(matched_req_names[:5])}")
        if missing_req_names:
            reason_parts.append(f"缺少: {', '.join(missing_req_names[:5])}")
    if preferred_norm:
        reason_parts.append(f"加分技能命中 {len(matched_pref)}/{len(preferred_norm)}")
        if matched_pref_names:
            reason_parts.append(f"加分匹配: {', '.join(matched_pref_names[:3])}")

    reason = "；".join(reason_parts) if reason_parts else "JD 未列出明确技能要求"

    return score, reason, matched_names, missing_names


# ── Project Scoring ────────────────────────────────────

_ACTION_KEYWORDS = [
    "开发", "设计", "实现", "搭建", "重构", "优化", "部署", "维护",
    "接口", "api", "数据库", "缓存", "模型", "训练", "推理",
    "性能", "并发", "分布式", "微服务", "自动化", "测试",
    "监控", "日志", "安全", "迁移", "上线",
    "develop", "design", "implement", "build", "refactor", "optimize",
    "deploy", "api", "database", "cache", "model", "train", "inference",
    "performance", "concurrent", "distributed", "microservice",
]

_QUANT_PATTERN = re.compile(
    r"\d+\s*[%％]|"
    r"\d+\s*[万kK]|"
    r"\d+\s*(?:ms|毫秒|秒|分钟|小时|QPS|TPS|RT)|"
    r"提升\s*\d+|降低\s*\d+|减少\s*\d+|增长\s*\d+|"
    r"improved?\s+by\s+\d+|reduced?\s+by\s+\d+|increased?\s+by\s+\d+"
)


def _score_projects(resume_parsed: dict, jd_parsed: dict) -> tuple[float, str]:
    """Evaluate project relevance and quality."""
    projects = resume_parsed.get("projects", [])
    if not projects:
        return 30.0, "简历中没有项目经历"

    # Keep both a lookup map and a key set.  The old code used a set and then
    # called `.get(...)` on it inside the project scoring loop, which raised:
    #   'set' object has no attribute 'get'
    # when analysis reached the project-overlap branch.
    jd_skill_map = {
        s.name.lower(): s.name
        for s in normalize_skills(jd_parsed.get("required_skills", []) + jd_parsed.get("preferred_skills", []))
    }
    jd_skills_norm = set(jd_skill_map.keys())

    total_proj_score = 0.0
    has_quantified = False
    has_action = False
    relevant_projects = 0
    best_overlap_names: list[str] = []

    for proj in projects:
        proj_score = 0.0
        desc = proj.get("description", "") + " " + " ".join(proj.get("achievements", []))
        tech_stack = proj.get("tech_stack", [])

        # Tech overlap with JD
        tech_norm = {s.name.lower() for s in normalize_skills(tech_stack)}
        overlap = tech_norm & jd_skills_norm
        if jd_skills_norm:
            ratio = len(overlap) / len(jd_skills_norm)
            proj_score += ratio * 40
            if ratio > 0.2:
                relevant_projects += 1
            # Track best overlapping tech names
            overlap_names = [jd_skill_map.get(k, k) for k in list(overlap)[:5]]
            best_overlap_names.extend(overlap_names)

        # Action keywords
        desc_lower = desc.lower()
        action_hits = sum(1 for kw in _ACTION_KEYWORDS if kw in desc_lower)
        if action_hits > 0:
            has_action = True
            proj_score += min(30, action_hits * 5)

        # Quantified metrics
        if _QUANT_PATTERN.search(desc):
            has_quantified = True
            proj_score += 20

        # Length bonus (substantial description)
        if len(desc) > 100:
            proj_score += 10

        total_proj_score += min(100, proj_score)

    avg_score = total_proj_score / len(projects)

    # Penalty if no quantification across all projects
    if not has_quantified:
        avg_score = min(avg_score, 60)

    # Build detailed reason
    reason_parts = [f"共 {len(projects)} 个项目"]
    if relevant_projects > 0:
        reason_parts.append(f"{relevant_projects} 个与岗位相关")
    if best_overlap_names:
        unique_names = list(dict.fromkeys(best_overlap_names))[:5]
        reason_parts.append(f"技术栈交集: {', '.join(unique_names)}")
    if has_quantified:
        reason_parts.append("有量化指标")
    else:
        reason_parts.append("缺少量化指标(建议补充性能/数据量/用户数等)")
    if has_action:
        reason_parts.append("有具体技术动作描述")

    return avg_score, "；".join(reason_parts)


# ── Semantic Scoring ───────────────────────────────────

def _score_semantic(resume_text: str, jd_text: str) -> tuple[float, str]:
    """Compute semantic relatedness on a human-readable 0-100 scale.

    Raw cosine/TF-IDF similarity for Chinese JD/resume text is often 0.01~0.05.
    Showing that directly as 1~5 分 is misleading, so this function calibrates the
    raw value and mixes in topic-keyword overlap.
    """
    if not resume_text.strip() or not jd_text.strip():
        return 35.0, "简历或 JD 文本为空，语义分按低置信度保底分处理"

    service = get_embedding_service()
    raw_similarity = service.compute_similarity(resume_text, jd_text)
    raw_similarity = max(0.0, min(1.0, float(raw_similarity or 0.0)))

    resume_terms = _semantic_terms(resume_text)
    jd_terms = _semantic_terms(jd_text)
    overlap = resume_terms & jd_terms

    if jd_terms:
        denominator = min(max(len(jd_terms), 1), 24)
        keyword_score = 35.0 + 60.0 * math.sqrt(min(len(overlap), denominator) / denominator)
    else:
        keyword_score = 55.0

    # Nonlinear calibration avoids 0.02 cosine becoming 2 分 while still keeping
    # irrelevant text below the recommended threshold.
    vector_score = 35.0 + 60.0 * math.sqrt(raw_similarity)
    score = _safe_score(vector_score * 0.62 + keyword_score * 0.38)
    score = max(35.0, min(95.0, score))

    reason = (
        f"文本相关度已校准：原始相似度 {raw_similarity:.3f}，"
        f"主题关键词交集 {len(overlap)} 个"
    )
    return score, reason


def _safe_score(value: float) -> float:
    try:
        value = float(value)
    except Exception:
        return 0.0
    return round(max(0.0, min(100.0, value)), 1)


def _semantic_terms(text: str) -> set[str]:
    text = text.lower()
    terms: set[str] = set()
    # English / technical tokens
    terms.update(re.findall(r"[a-z][a-z0-9+#.]{1,}", text))
    # Common Chinese technical / role terms. This keeps the implementation
    # dependency-free while being more stable than single-character overlap.
    common = [
        "后端", "前端", "全栈", "算法", "数据", "产品", "运营", "测试", "设计", "实习",
        "开发", "工程师", "经理", "分析", "机器学习", "深度学习", "大模型", "自然语言",
        "python", "java", "go", "javascript", "typescript", "react", "vue", "fastapi",
        "django", "flask", "spring", "mysql", "redis", "mongodb", "docker", "kubernetes",
        "linux", "git", "sql", "api", "接口", "数据库", "模型", "训练", "推理",
        "需求", "prd", "原型", "用户", "增长", "项目管理", "自动化", "性能", "部署",
    ]
    for term in common:
        if term.lower() in text:
            terms.add(term.lower())
    # Add medium-length Chinese chunks; filter generic fragments.
    stop = {"岗位", "职位", "要求", "职责", "公司", "团队", "相关", "优先", "经验", "能力", "熟悉", "掌握"}
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,8}", text):
        if chunk not in stop:
            terms.add(chunk)
    return terms


# ── Requirement Scoring ────────────────────────────────

_DEGREE_HIERARCHY = {
    "博士": 4, "phd": 4, "doctor": 4,
    "硕士": 3, "master": 3, "研究生": 3, "mba": 3,
    "本科": 2, "学士": 2, "bachelor": 2,
    "大专": 1, "专科": 1, "associate": 1,
}


def _score_requirements(
    resume_parsed: dict, jd_parsed: dict
) -> tuple[float, str]:
    """Check hard requirements: education, experience, etc."""
    checks: list[tuple[Optional[bool], str]] = []

    # Education
    edu_req = jd_parsed.get("education_requirement", "").strip()
    if edu_req:
        resume_edu = resume_parsed.get("education", [])
        edu_matched = _check_education(resume_edu, edu_req)
        checks.append((edu_matched, f"学历要求: {edu_req}"))

    # Experience
    exp_req = jd_parsed.get("experience_requirement", "").strip()
    if exp_req:
        resume_exp_years = _extract_years(resume_parsed)
        exp_matched = _check_experience(resume_exp_years, exp_req)
        checks.append((exp_matched, f"经验要求: {exp_req}"))

    if not checks:
        return 70.0, "JD 未列出明确硬性要求，给予中性分"

    scores = []
    for matched, desc in checks:
        if matched is True:
            scores.append(100)
        elif matched is None:
            scores.append(60)
        else:
            scores.append(30)

    avg = sum(scores) / len(scores)
    passed = sum(1 for m, _ in checks if m is True)
    reason = f"满足 {passed}/{len(checks)} 项硬性要求"

    return avg, reason


def _check_education(resume_edu: list[dict], edu_req: str) -> Optional[bool]:
    """Check if resume education meets the requirement."""
    if not resume_edu:
        return None

    max_degree = 0
    for edu in resume_edu:
        degree = edu.get("degree", "").strip().lower()
        for key, level in _DEGREE_HIERARCHY.items():
            if key in degree:
                max_degree = max(max_degree, level)
                break

    req_level = 0
    edu_req_lower = edu_req.lower()
    for key, level in _DEGREE_HIERARCHY.items():
        if key in edu_req_lower:
            req_level = max(req_level, level)
            break

    if req_level == 0:
        return None

    return max_degree >= req_level


def _extract_years(resume_parsed: dict) -> Optional[int]:
    """Try to extract total years of experience from resume."""
    years_str = resume_parsed.get("basic_info", {}).get("years_of_experience", "")
    if years_str:
        match = re.search(r"(\d+)", years_str)
        if match:
            return int(match.group(1))

    total_months = 0
    for exp in resume_parsed.get("work_experience", []):
        start = exp.get("start_date", "")
        end = exp.get("end_date", "")
        months = _estimate_months(start, end)
        if months:
            total_months += months

    if total_months > 0:
        return total_months // 12

    return None


def _estimate_months(start: str, end: str) -> Optional[int]:
    """Estimate months between two date strings."""
    start_match = re.search(r"(\d{4})[\.\-/](\d{1,2})", start)
    if not start_match:
        return None
    start_year, start_month = int(start_match.group(1)), int(start_match.group(2))

    if "至今" in end or "present" in end.lower():
        from datetime import datetime
        now = datetime.now()
        end_year, end_month = now.year, now.month
    else:
        end_match = re.search(r"(\d{4})[\.\-/](\d{1,2})", end)
        if not end_match:
            return None
        end_year, end_month = int(end_match.group(1)), int(end_match.group(2))

    return max(0, (end_year - start_year) * 12 + (end_month - start_month))


def _check_experience(resume_years: Optional[int], exp_req: str) -> Optional[bool]:
    """Check if resume experience meets the requirement."""
    if resume_years is None:
        return None

    req_match = re.search(r"(\d+)", exp_req)
    if not req_match:
        return None

    req_years = int(req_match.group(1))
    return resume_years >= req_years
