"""Resume diagnosis service.

Rule-based engine that detects 10 types of resume issues
and provides evidence, reasons, and actionable suggestions.
"""

import re

from app.schemas.diagnosis import DiagnosisIssue
from app.services.skill_normalizer import normalize_skills


def diagnose(
    resume_parsed: dict,
    jd_parsed: dict,
    matched_skills: list[str],
    missing_skills: list[str],
) -> list[DiagnosisIssue]:
    """Run all diagnosis checks and return a list of issues."""
    issues: list[DiagnosisIssue] = []

    issues.extend(_check_missing_required_skill(jd_parsed, missing_skills))
    issues.extend(_check_weak_project_description(resume_parsed))
    issues.extend(_check_lack_of_metrics(resume_parsed))
    issues.extend(_check_skill_not_reflected(resume_parsed, matched_skills))
    issues.extend(_check_irrelevant_project(resume_parsed, jd_parsed))
    issues.extend(_check_unclear_role(resume_parsed))
    issues.extend(_check_vague_action(resume_parsed))
    issues.extend(_check_missing_business_context(resume_parsed))
    issues.extend(_check_missing_technical_detail(resume_parsed))
    issues.extend(_check_format_issue(resume_parsed))

    return issues


# ── Check 1: missing_required_skill ────────────────────

def _check_missing_required_skill(
    jd_parsed: dict, missing_skills: list[str]
) -> list[DiagnosisIssue]:
    if not missing_skills:
        return []

    issues = []
    for skill in missing_skills[:5]:  # Cap at 5 to avoid overwhelming
        issues.append(DiagnosisIssue(
            type="missing_required_skill",
            severity="high",
            title=f"缺少必备技能: {skill}",
            evidence=f"JD 要求具备 [{skill}] 技能，简历中未找到相关描述",
            reason=f"该技能是岗位核心要求，缺失会直接影响简历筛选通过率",
            suggestion=f"如果你掌握 {skill}，请在技能栏或项目经历中补充；如果尚未掌握，建议尽快学习并在简历中体现学习成果",
            rewrite_example=f"技能栏添加: {skill} | 项目描述中补充: 使用 {skill} 完成了...",
        ))

    return issues


# ── Check 2: weak_project_description ──────────────────

_WEAK_PATTERNS = [
    r"^负责.{2,8}$",
    r"^参与.{2,8}$",
    r"^完成.{2,8}$",
    r"^开发.{2,8}$",
    r"^学习.{2,8}$",
]


def _check_weak_project_description(resume_parsed: dict) -> list[DiagnosisIssue]:
    issues = []
    for proj in resume_parsed.get("projects", []):
        desc = proj.get("description", "").strip()
        name = proj.get("name", "未命名项目")

        if not desc:
            issues.append(DiagnosisIssue(
                type="weak_project_description",
                severity="high",
                title=f"项目 [{name}] 缺少描述",
                evidence=f"项目 [{name}] 的 description 字段为空",
                reason="没有项目描述，面试官无法了解你做了什么",
                suggestion="用 STAR 法则描述：在什么场景下(S)，承担什么任务(T)，采取了什么行动(A)，取得什么结果(R)",
                rewrite_example="示例: 在XX系统中(S)，负责用户认证模块开发(T)，采用 JWT + Redis 实现 Token 管理(A)，支持 10万+ 用户并发登录(R)",
            ))
            continue

        # Check if description is too short
        if len(desc) < 20:
            issues.append(DiagnosisIssue(
                type="weak_project_description",
                severity="medium",
                title=f"项目 [{name}] 描述过于简短",
                evidence=f"项目 [{name}] 描述仅 {len(desc)} 字: \"{desc}\"",
                reason="简短的描述无法体现你的技术深度和贡献",
                suggestion="扩展描述，补充具体技术栈、你的职责、遇到的挑战和解决方案",
                rewrite_example=f"在原描述基础上扩展: {desc} + 使用 [技术栈] 实现了 [具体功能]，解决了 [具体问题]",
            ))
            continue

        # Check if it's just a generic phrase
        for pattern in _WEAK_PATTERNS:
            if re.match(pattern, desc) and len(desc) < 30:
                issues.append(DiagnosisIssue(
                    type="weak_project_description",
                    severity="medium",
                    title=f"项目 [{name}] 描述过于笼统",
                    evidence=f"项目 [{name}] 描述: \"{desc}\"",
                    reason="描述只有动作没有细节，无法判断你的实际贡献和技术能力",
                    suggestion="拆解具体工作内容，补充技术方案和量化结果",
                    rewrite_example=f"原: {desc} → 改: {desc}，采用 [具体技术] 实现了 [具体功能]，[量化结果]",
                ))
                break

    return issues


# ── Check 3: lack_of_metrics ───────────────────────────

_METRIC_PATTERN = re.compile(
    r"\d+\s*[%％]|"
    r"\d+\s*[万kK]|"
    r"\d+\s*(?:ms|毫秒|秒|分钟|小时|QPS|TPS|RT|DAU|PV|UV)|"
    r"提升\s*\d+|降低\s*\d+|减少\s*\d+|增长\s*\d+|"
    r"improved?\s+by\s+\d+|reduced?\s+by\s+\d+|increased?\s+by\s+\d+|"
    r"\d+\s*(?:个|条|次|台|节点|服务|接口|模块)"
)


def _check_lack_of_metrics(resume_parsed: dict) -> list[DiagnosisIssue]:
    projects = resume_parsed.get("projects", [])
    if not projects:
        return []

    projects_without_metrics = []
    for proj in projects:
        desc = proj.get("description", "") + " " + " ".join(proj.get("achievements", []))
        if not _METRIC_PATTERN.search(desc):
            projects_without_metrics.append(proj.get("name", "未命名项目"))

    if not projects_without_metrics:
        return []

    return [DiagnosisIssue(
        type="lack_of_metrics",
        severity="medium",
        title="项目经历缺少量化指标",
        evidence=f"以下项目没有包含任何数字或量化数据: {', '.join(projects_without_metrics[:3])}",
        reason="没有量化数据的描述缺乏说服力，面试官无法评估你的贡献大小",
        suggestion="为每个项目补充至少一个量化指标，如: 性能提升百分比、处理数据量、并发数、用户数、响应时间等",
        rewrite_example="原: 负责后端接口开发 → 改: 开发了 15+ 个 RESTful API 接口，支撑日均 50万次调用，平均响应时间 < 100ms",
    )]


# ── Check 4: skill_not_reflected_in_project ────────────

def _check_skill_not_reflected(
    resume_parsed: dict, matched_skills: list[str]
) -> list[DiagnosisIssue]:
    if not matched_skills:
        return []

    # Collect all skills mentioned in projects
    project_text = ""
    for proj in resume_parsed.get("projects", []):
        project_text += " ".join(proj.get("tech_stack", [])) + " "
        project_text += proj.get("description", "") + " "

    project_text_lower = project_text.lower()

    not_reflected = []
    for skill in matched_skills:
        if skill.lower() not in project_text_lower:
            not_reflected.append(skill)

    if not not_reflected:
        return []

    return [DiagnosisIssue(
        type="skill_not_reflected_in_project",
        severity="medium",
        title="技能栈未在项目中体现",
        evidence=f"以下技能在简历技能栏列出，但在项目经历中没有体现: {', '.join(not_reflected[:5])}",
        reason="只列技能名称没有说服力，面试官会怀疑你是否真正使用过这些技术",
        suggestion="在项目描述中补充这些技术的具体使用场景",
        rewrite_example=f"在相关项目中补充: 使用 {not_reflected[0]} 实现了 [具体功能]，解决了 [具体问题]",
    )]


# ── Check 5: irrelevant_project ────────────────────────

def _check_irrelevant_project(
    resume_parsed: dict, jd_parsed: dict
) -> list[DiagnosisIssue]:
    projects = resume_parsed.get("projects", [])
    if not projects:
        return []

    jd_skills_norm = {s.name.lower() for s in normalize_skills(
        jd_parsed.get("required_skills", []) + jd_parsed.get("preferred_skills", [])
    )}
    jd_keywords = set(jd_parsed.get("keywords", []))
    jd_responsibilities = " ".join(jd_parsed.get("responsibilities", [])).lower()

    irrelevant = []
    for proj in projects:
        tech_stack = proj.get("tech_stack", [])
        desc = proj.get("description", "").lower()
        name = proj.get("name", "未命名项目")

        tech_norm = {s.name.lower() for s in normalize_skills(tech_stack)}
        tech_overlap = tech_norm & jd_skills_norm

        # Check keyword overlap
        desc_words = set(re.findall(r"[一-鿿]{2,}|[a-z]+", desc))
        keyword_overlap = desc_words & jd_keywords

        # Check responsibility overlap
        resp_hits = sum(1 for kw in desc_words if kw in jd_responsibilities and len(kw) > 2)

        if len(tech_overlap) == 0 and len(keyword_overlap) == 0 and resp_hits < 2:
            irrelevant.append(name)

    if not irrelevant:
        return []

    return [DiagnosisIssue(
        type="irrelevant_project",
        severity="low",
        title="部分项目与目标岗位相关性弱",
        evidence=f"以下项目的技术栈和描述与 JD 要求匹配度较低: {', '.join(irrelevant[:3])}",
        reason="不相关的项目会稀释你的竞争力，建议聚焦展示与岗位相关的项目",
        suggestion="优先展示与目标岗位最相关的项目；如果项目较少，可以从无关项目中提取可迁移的技术能力",
        rewrite_example="从无关项目中提取通用能力: 如 从游戏开发项目中提取 性能优化、并发处理 经验",
    )]


# ── Check 6: unclear_role ──────────────────────────────

_ROLE_VAGUE = re.compile(r"^(参与|负责|协助|完成|进行|从事)")


def _check_unclear_role(resume_parsed: dict) -> list[DiagnosisIssue]:
    issues = []
    for proj in resume_parsed.get("projects", []):
        role = proj.get("role", "").strip()
        name = proj.get("name", "未命名项目")

        if not role:
            issues.append(DiagnosisIssue(
                type="unclear_role",
                severity="medium",
                title=f"项目 [{name}] 未说明你的角色",
                evidence=f"项目 [{name}] 的 role 字段为空",
                reason="不清楚你在项目中的角色，面试官无法判断你的职责范围和贡献大小",
                suggestion="明确你的角色: 如 后端开发、全栈开发、技术负责人、核心开发者等",
                rewrite_example=f"角色: 核心后端开发 | 负责用户系统和订单模块的设计与实现",
            ))
        elif _ROLE_VAGUE.match(role) and len(role) < 10:
            issues.append(DiagnosisIssue(
                type="unclear_role",
                severity="low",
                title=f"项目 [{name}] 角色描述模糊",
                evidence=f"项目 [{name}] 角色: \"{role}\"",
                reason="模糊的角色描述无法体现你的具体贡献",
                suggestion="用更具体的职责描述替代泛泛的动词",
                rewrite_example=f"原: {role} → 改: 负责后端 API 设计与实现，主导数据库方案选型",
            ))

    return issues


# ── Check 7: vague_action ──────────────────────────────

_VAGUE_ACTIONS = {
    "参与": "具体说明你参与了哪个环节，做了什么",
    "负责": "拆解具体负责的内容，如负责XX模块的接口设计与实现",
    "了解": "了解不算经验，建议改为实际使用过的描述",
    "熟悉": "熟悉太主观，建议用具体项目经验证明",
    "学习": "学习不算项目经验，建议展示学习后的实践成果",
    "协助": "协助无法体现你的贡献，建议说明你具体做了什么",
}


def _check_vague_action(resume_parsed: dict) -> list[DiagnosisIssue]:
    issues = []
    for proj in resume_parsed.get("projects", []):
        desc = proj.get("description", "")
        name = proj.get("name", "未命名项目")

        for vague, fix in _VAGUE_ACTIONS.items():
            if vague in desc and len(desc) < 50:
                issues.append(DiagnosisIssue(
                    type="vague_action",
                    severity="medium",
                    title=f"项目 [{name}] 使用了模糊表达 \"{vague}\"",
                    evidence=f"项目 [{name}] 描述中包含 \"{vague}\"",
                    reason=f"\"{vague}\" 是简历中的高频模糊词，无法体现具体贡献",
                    suggestion=fix,
                    rewrite_example=f"原: {desc} → 改: 用具体动作替代 \"{vague}\"，如 设计、开发、优化、部署",
                ))
                break  # One issue per project

    return issues


# ── Check 8: missing_business_context ──────────────────

def _check_missing_business_context(resume_parsed: dict) -> list[DiagnosisIssue]:
    issues = []
    for proj in resume_parsed.get("projects", []):
        desc = proj.get("description", "").strip()
        name = proj.get("name", "未命名项目")

        if not desc:
            continue

        # Check if there's any business context
        has_context = any(kw in desc for kw in [
            "场景", "业务", "用户", "客户", "需求", "背景", "目标",
            "为了解决", "为了提升", "为了优化", "针对",
            "scenario", "business", "user", "customer", "requirement",
        ])

        if not has_context and len(desc) > 30:
            issues.append(DiagnosisIssue(
                type="missing_business_context",
                severity="low",
                title=f"项目 [{name}] 缺少业务背景",
                evidence=f"项目 [{name}] 描述中没有体现业务场景或项目背景",
                reason="缺少业务背景的描述会让项目显得脱离实际，面试官难以理解项目价值",
                suggestion="在项目开头补充一句业务背景: 为什么做这个项目，解决什么问题",
                rewrite_example=f"补充背景: 为了解决XX业务场景下的YY问题，开发了ZZ系统，...",
            ))

    return issues


# ── Check 9: missing_technical_detail ──────────────────

_TECH_DETAIL_KEYWORDS = [
    "架构", "设计模式", "算法", "数据结构", "协议", "缓存策略",
    "分库分表", "索引", "事务", "锁", "队列", "异步", "并发",
    "负载均衡", "熔断", "降级", "限流", "监控", "日志",
    "docker", "kubernetes", "微服务", "分布式", "集群",
    "redis", "mysql", "mongodb", "elasticsearch",
    "jwt", "oauth", "https", "加密", "认证", "授权",
]


def _check_missing_technical_detail(resume_parsed: dict) -> list[DiagnosisIssue]:
    issues = []
    for proj in resume_parsed.get("projects", []):
        desc = proj.get("description", "").lower()
        name = proj.get("name", "未命名项目")

        if not desc or len(desc) < 30:
            continue

        tech_hits = sum(1 for kw in _TECH_DETAIL_KEYWORDS if kw in desc)

        if tech_hits == 0:
            issues.append(DiagnosisIssue(
                type="missing_technical_detail",
                severity="medium",
                title=f"项目 [{name}] 缺少技术实现细节",
                evidence=f"项目 [{name}] 描述中没有提到具体的技术方案、架构设计或实现细节",
                reason="没有技术细节的描述无法体现你的技术深度，面试官无法评估你的技术能力",
                suggestion="补充你使用的技术方案: 数据库选型理由、缓存策略、接口设计、部署方案等",
                rewrite_example=f"补充技术细节: 采用 XX 架构，使用 YY 数据库存储，通过 ZZ 缓存热点数据，接口响应时间优化到 NN ms",
            ))

    return issues


# ── Check 10: format_issue ─────────────────────────────

def _check_format_issue(resume_parsed: dict) -> list[DiagnosisIssue]:
    issues = []

    # Check basic info
    basic = resume_parsed.get("basic_info", {})
    if not basic.get("name"):
        issues.append(DiagnosisIssue(
            type="format_issue",
            severity="medium",
            title="缺少姓名信息",
            evidence="简历基本信息中 name 字段为空",
            reason="姓名是简历最基本的信息，缺失会影响 HR 联系你",
            suggestion="在简历开头明确写出姓名",
            rewrite_example="在简历顶部添加: 姓名: XXX",
        ))

    if not basic.get("phone") and not basic.get("email"):
        issues.append(DiagnosisIssue(
            type="format_issue",
            severity="high",
            title="缺少联系方式",
            evidence="简历中没有手机号和邮箱",
            reason="没有联系方式，HR 无法联系你面试",
            suggestion="至少提供手机号或邮箱中的一个",
            rewrite_example="在基本信息中添加: 手机: 138xxxx1234 | 邮箱: xxx@email.com",
        ))

    # Check if skills section exists
    skills = resume_parsed.get("skills", [])
    if not skills:
        issues.append(DiagnosisIssue(
            type="format_issue",
            severity="medium",
            title="缺少技能清单",
            evidence="简历中没有明确的技能列表",
            reason="没有技能清单会让简历缺少关键词，影响 ATS 系统筛选",
            suggestion="在简历中添加一个技能清单部分，列出你掌握的核心技术",
            rewrite_example="添加技能清单: 编程语言: Python, Go | 框架: FastAPI, Django | 数据库: MySQL, Redis",
        ))

    return issues
