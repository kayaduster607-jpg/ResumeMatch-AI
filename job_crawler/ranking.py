from __future__ import annotations

import math
import os
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .models import JobItem, clean_text


# Canonical skill/keyword dictionary used by the standalone scorer. It covers
# software, AI/data, product, operations, design, and common workplace keywords.
SKILL_ALIASES: dict[str, list[str]] = {
    # Programming / backend / frontend
    "Python": ["python", "py"],
    "Java": ["java"],
    "Go": ["go", "golang"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "JavaScript": ["javascript", "js", "es6"],
    "TypeScript": ["typescript", "ts"],
    "HTML/CSS": ["html", "css", "html5", "css3"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "React": ["react", "react.js", "reactjs"],
    "Node.js": ["node.js", "nodejs", "node"],
    "Spring Boot": ["spring boot", "springboot", "spring"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "RESTful API": ["restful", "rest api", "api接口", "接口开发"],
    "微服务": ["微服务", "microservice", "microservices"],
    # Data / infra
    "SQL": ["sql"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Redis": ["redis"],
    "MongoDB": ["mongodb", "mongo"],
    "Kafka": ["kafka"],
    "Flink": ["flink"],
    "Spark": ["spark"],
    "Hadoop": ["hadoop"],
    "Docker": ["docker", "容器化"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Linux": ["linux"],
    "Git": ["git", "github", "gitlab"],
    "Nginx": ["nginx"],
    # AI / data science
    "机器学习": ["机器学习", "machine learning", "ml"],
    "深度学习": ["深度学习", "deep learning", "dl"],
    "PyTorch": ["pytorch", "torch"],
    "TensorFlow": ["tensorflow", "tf"],
    "NLP": ["nlp", "自然语言处理"],
    "大模型": ["大模型", "llm", "large language model", "gpt", "glm", "qwen", "通义", "文心"],
    "RAG": ["rag", "检索增强", "知识库问答"],
    "Prompt": ["prompt", "提示词", "提示工程"],
    "LangChain": ["langchain"],
    "Agent": ["agent", "智能体"],
    "数据分析": ["数据分析", "data analysis", "数据运营", "指标分析"],
    "数据挖掘": ["数据挖掘", "data mining"],
    "A/B测试": ["a/b", "abtest", "ab test", "a/b测试"],
    "Excel": ["excel"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    # Product / business
    "产品经理": ["产品经理", "产品助理", "产品实习", "pm"],
    "需求分析": ["需求分析", "需求调研", "需求文档", "需求梳理"],
    "PRD": ["prd", "产品需求文档"],
    "原型设计": ["原型", "原型设计", "axure", "墨刀", "figma"],
    "竞品分析": ["竞品分析", "竞品调研"],
    "用户调研": ["用户调研", "用户访谈", "问卷", "可用性测试"],
    "产品规划": ["产品规划", "路线图", "roadmap"],
    "项目管理": ["项目管理", "进度管理", "跨部门", "协同", "推进"],
    "B端产品": ["b端", "b2b", "企业级", "saas"],
    "C端产品": ["c端", "c2c", "用户增长", "app产品"],
    "增长": ["增长", "拉新", "留存", "转化", "转化率"],
    # Operations / marketing
    "运营": ["运营", "用户运营", "内容运营", "产品运营", "社群运营", "活动运营"],
    "新媒体": ["新媒体", "公众号", "小红书", "抖音", "视频号"],
    "电商": ["电商", "淘宝", "天猫", "京东", "拼多多", "shopify"],
    "SEO": ["seo", "搜索优化"],
    "SEM": ["sem", "投放", "广告投放"],
    "CRM": ["crm", "客户关系"],
    # Design / testing / QA
    "UI设计": ["ui", "ui设计", "界面设计"],
    "UX设计": ["ux", "用户体验", "交互设计"],
    "Figma": ["figma"],
    "Photoshop": ["photoshop", "ps"],
    "自动化测试": ["自动化测试", "selenium", "pytest", "接口测试"],
    "测试": ["测试", "qa", "质量保障"],
}

COMMON_SKILLS = list(SKILL_ALIASES)

ROLE_TERMS = [
    "后端", "前端", "全栈", "算法", "数据", "产品", "运营", "测试", "设计", "实习",
    "校招", "开发", "工程师", "助理", "经理", "分析师", "管培生", "销售", "市场",
]

ACTION_KEYWORDS = [
    "开发", "设计", "实现", "搭建", "重构", "优化", "部署", "维护", "负责", "推进", "协同",
    "接口", "数据库", "缓存", "模型", "训练", "推理", "性能", "并发", "分布式", "自动化",
    "测试", "监控", "日志", "上线", "调研", "分析", "规划", "撰写", "复盘", "增长",
    "develop", "design", "implement", "build", "refactor", "optimize", "deploy", "analyze",
]

DOMAIN_TERMS = sorted(set(COMMON_SKILLS + ROLE_TERMS + ACTION_KEYWORDS), key=len, reverse=True)

METRIC_PATTERN = re.compile(
    r"\d+\s*[%％]|"
    r"\d+\s*[万kK]|"
    r"\d+\s*(?:ms|毫秒|秒|分钟|小时|QPS|TPS|RT|DAU|PV|UV)|"
    r"提升\s*\d+|降低\s*\d+|减少\s*\d+|增长\s*\d+|"
    r"improved?\s+by\s+\d+|reduced?\s+by\s+\d+|increased?\s+by\s+\d+|"
    r"\d+\s*(?:个|条|次|台|节点|服务|接口|模块|用户|订单|客户)"
)

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "you", "your", "job", "work",
    "岗位", "职位", "要求", "职责", "公司", "团队", "相关", "优先", "经验", "能力", "熟悉", "掌握",
}

DEGREE_LEVELS = {
    "博士": 4, "phd": 4, "doctor": 4,
    "硕士": 3, "研究生": 3, "master": 3, "mba": 3,
    "本科": 2, "学士": 2, "bachelor": 2,
    "大专": 1, "专科": 1, "associate": 1,
}


def read_resume_text(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"简历文件不存在：{path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def _read_pdf(path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError("读取 PDF 简历需要 PyMuPDF；请先安装 backend/requirements.txt 或把简历转为 txt/docx。") from exc
    doc = fitz.open(path)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _read_docx(path: Path) -> str:
    # Minimal DOCX text extraction with stdlib; avoids requiring python-docx.
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", ns):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
        line = "".join(texts).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def rank_jobs(
    resume_path: str | Path,
    jobs: list[JobItem],
    *,
    min_score: float = 0,
    top: int = 50,
    keyword: str = "",
) -> tuple[list[JobItem], dict[str, Any]]:
    """Score every job against the resume and return sorted jobs.

    Default scoring is a calibrated standalone scorer. It deliberately maps all
    dimensions to a 0-100 human-readable scale, avoiding the tiny similarity
    numbers often produced by raw text/vector similarity.
    """
    resume_text = read_resume_text(resume_path)
    if not resume_text.strip():
        raise RuntimeError("简历文本为空，请换成可解析的 txt/pdf/docx 简历。")

    meta: dict[str, Any] = {
        "resume_path": str(resume_path),
        "resume_chars": len(resume_text),
        "scoring_engine": "enhanced_rule_v2",
        "score_scale": "0-100；85+强匹配，75-84推荐投递，60-74可投递需优化，50-59低优先级，50以下不建议优先",
    }

    engine = os.environ.get("JOB_CRAWLER_SCORING_ENGINE", "enhanced").strip().lower()
    if engine == "backend":
        try:
            _rank_with_backend(resume_text, jobs)
            meta["scoring_engine"] = "backend"
        except Exception as exc:
            meta["scoring_engine"] = "enhanced_rule_v2"
            meta["backend_error"] = f"backend 评分失败，已自动切换为增强规则评分：{exc}"
            _rank_with_enhanced_rules(resume_text, jobs, keyword=keyword)
    else:
        _rank_with_enhanced_rules(resume_text, jobs, keyword=keyword)

    ranked = [job for job in jobs if job.total_score >= min_score]
    ranked.sort(key=lambda j: (j.total_score, j.skill_score, j.requirement_score, len(j.matched_skills)), reverse=True)
    if top and top > 0:
        ranked = ranked[:top]
    return ranked, meta


def _rank_with_enhanced_rules(resume_text: str, jobs: list[JobItem], *, keyword: str = "") -> None:
    resume_skills = _extract_common_skills(resume_text)
    resume_terms = _semantic_terms(resume_text)
    resume_degree = _extract_degree_level(resume_text)
    resume_years = _extract_resume_years(resume_text)

    for job in jobs:
        jd_text = job.raw_text()
        jd_skills = _extract_common_skills(jd_text)
        matched = _sort_skills(resume_skills & jd_skills)
        missing = _sort_skills(jd_skills - resume_skills)

        skill_score, skill_reason = _score_skills_enhanced(resume_skills, jd_skills, matched)
        project_score, project_reason = _score_project_enhanced(resume_text, matched)
        semantic_score, semantic_reason = _score_semantic_enhanced(resume_terms, jd_text, keyword, job)
        requirement_score, requirement_reason = _score_requirements_enhanced(
            resume_text=resume_text,
            jd_text=jd_text,
            job=job,
            resume_degree=resume_degree,
            resume_years=resume_years,
        )

        total = (
            skill_score * 0.38
            + project_score * 0.22
            + semantic_score * 0.25
            + requirement_score * 0.15
        )
        # If the title/description barely relates to the query, keep the score
        # from looking deceptively high.
        keyword_score = _keyword_relevance(keyword, job)
        if keyword and keyword_score < 55:
            total = min(total, 49.0)
        elif keyword and keyword_score < 65:
            total = min(total, 58.0)

        job.total_score = round(_clamp(total, 0, 100), 1)
        job.skill_score = round(skill_score, 1)
        job.project_score = round(project_score, 1)
        job.semantic_score = round(semantic_score, 1)
        job.requirement_score = round(requirement_score, 1)
        job.matched_skills = matched
        job.missing_skills = missing
        job.match_level, job.recommendation = _level_and_recommendation(job.total_score)
        job.optimization_suggestions = _enhanced_suggestions(job, keyword, resume_text)
        job.score_reason = "；".join([skill_reason, project_reason, semantic_reason, requirement_reason])


def _score_skills_enhanced(resume_skills: set[str], jd_skills: set[str], matched: list[str]) -> tuple[float, str]:
    if not jd_skills:
        return 65.0, "技能：JD 未识别出明确技能标签，给予中性分"
    if not resume_skills:
        return 42.0, f"技能：JD 有 {len(jd_skills)} 个技能点，但简历未识别出技能关键词"

    # Many JDs list a broad wish list. Cap the denominator so one long JD does
    # not unfairly push the score to 1-2 points.
    effective_total = min(max(len(jd_skills), 1), 8)
    coverage = min(len(matched), effective_total) / effective_total
    score = 38 + 57 * coverage
    if len(matched) >= 3:
        score += 4
    if len(matched) >= 5:
        score += 3
    score = _clamp(score, 35, 98)
    return score, f"技能：命中 {len(matched)}/{len(jd_skills)} 个可识别技能，按最多 8 个核心技能校准"


def _score_project_enhanced(resume_text: str, matched_skills: list[str]) -> tuple[float, str]:
    text = resume_text.lower()
    has_project = bool(re.search(r"项目经历|项目经验|个人项目|项目[：:]|作品|案例", resume_text))
    has_work = bool(re.search(r"工作经历|实习经历|任职|负责|参与|岗位|公司", resume_text))
    action_hits = sum(1 for kw in ACTION_KEYWORDS if kw.lower() in text)
    has_metric = bool(METRIC_PATTERN.search(resume_text))

    score = 42.0
    if has_project:
        score += 18
    if has_work:
        score += 10
    score += min(action_hits, 8) * 2.8
    score += min(len(matched_skills), 5) * 3.0
    if has_metric:
        score += 10
    if len(resume_text) > 800:
        score += 4

    if not has_project and not has_work:
        score = min(score, 55)
    if not has_metric:
        score = min(score, 78)

    parts = []
    parts.append("有项目/作品描述" if has_project else "项目描述不明显")
    parts.append("有工作/实习经历" if has_work else "工作/实习经历不明显")
    parts.append("有量化指标" if has_metric else "量化指标不足")
    return _clamp(score, 35, 95), "项目：" + "，".join(parts)


def _score_semantic_enhanced(resume_terms: set[str], jd_text: str, keyword: str, job: JobItem) -> tuple[float, str]:
    jd_terms = _semantic_terms(jd_text)
    if not jd_terms:
        base = 58.0
        overlap_count = 0
    else:
        overlap = resume_terms & jd_terms
        overlap_count = len(overlap)
        denominator = min(max(len(jd_terms), 1), 20)
        coverage = min(overlap_count, denominator) / denominator
        # Nonlinear mapping: raw overlap is often small for Chinese text, so use
        # sqrt calibration to keep scores interpretable.
        base = 42 + 50 * math.sqrt(coverage)
    keyword_score = _keyword_relevance(keyword, job)
    score = base * 0.72 + keyword_score * 0.28
    reason = f"文本：岗位关键词相关度 {keyword_score:.0f}，简历/JD 主题交集 {overlap_count} 个"
    return _clamp(score, 35, 95), reason


def _score_requirements_enhanced(
    *,
    resume_text: str,
    jd_text: str,
    job: JobItem,
    resume_degree: int | None,
    resume_years: int | None,
) -> tuple[float, str]:
    combined_jd = " ".join([job.degree, job.experience, jd_text])
    if re.search(r"学历不限|经验不限|不限经验|应届|实习", combined_jd):
        relaxed = True
    else:
        relaxed = False

    required_degree = _extract_degree_requirement(combined_jd)
    required_years = _extract_required_years(combined_jd)
    score = 88.0
    notes: list[str] = []

    if required_degree:
        if resume_degree is None:
            score -= 6
            notes.append("简历学历未明确")
        elif resume_degree < required_degree:
            score -= 24
            notes.append("学历可能低于要求")
        else:
            notes.append("学历基本满足")
    else:
        notes.append("学历要求不明确/不限")

    if required_years is not None:
        if resume_years is None:
            penalty = 12 if required_years >= 3 else 5
            score -= penalty
            notes.append("简历年限未明确")
        elif resume_years < required_years:
            score -= 18
            notes.append(f"经验年限可能不足：简历约 {resume_years} 年，JD 要求 {required_years}+ 年")
        else:
            notes.append("经验年限基本满足")
    else:
        notes.append("经验要求不严格")

    if relaxed:
        score = max(score, 84)

    return _clamp(score, 35, 98), "硬性要求：" + "，".join(notes)


def _extract_common_skills(text: str) -> set[str]:
    low = _norm_for_match(text)
    found: set[str] = set()
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if _alias_in_text(alias, low):
                found.add(canonical)
                break
    return found


def _semantic_terms(text: str) -> set[str]:
    low = _norm_for_match(text)
    terms: set[str] = set()
    terms.update(_extract_common_skills(text))
    for term in DOMAIN_TERMS:
        if term in SKILL_ALIASES:
            continue
        if _alias_in_text(term, low):
            terms.add(term)
    for word in re.findall(r"[a-z][a-z0-9+#.]{1,}", low):
        if word not in STOPWORDS and len(word) >= 2:
            terms.add(word)
    # Add a small number of Chinese phrase chunks. This helps non-technical JDs
    # without requiring jieba.
    for chunk in re.findall(r"[一-鿿]{2,8}", clean_text(text)):
        if chunk not in STOPWORDS and len(chunk) >= 2:
            terms.add(chunk)
    return terms


def _keyword_relevance(keyword: str, job: JobItem) -> float:
    keyword = clean_text(keyword)
    if not keyword:
        return 65.0
    terms = _query_terms(keyword)
    title = _norm_for_match(job.title)
    haystack = _norm_for_match(job.raw_text())
    full = _norm_for_match(keyword)

    if full and full in title:
        return 96.0
    if terms and all(t in title for t in terms):
        return 92.0
    if terms:
        title_hits = sum(1 for t in terms if t in title)
        all_hits = sum(1 for t in terms if t in haystack)
        if title_hits:
            return 72.0 + min(20.0, title_hits / len(terms) * 20.0)
        if all_hits == len(terms):
            return 74.0
        if all_hits:
            return 58.0 + min(16.0, all_hits / len(terms) * 16.0)
    return 48.0


def _query_terms(keyword: str) -> list[str]:
    low = _norm_for_match(keyword)
    terms: list[str] = []
    for part in re.split(r"[,，/|\s]+", low):
        if part and part not in terms:
            terms.append(part)
    for hint in ROLE_TERMS + COMMON_SKILLS:
        h = _norm_for_match(hint)
        if h and h in low and h not in terms:
            terms.append(h)
    # Common mixed query, e.g. AI开发实习生.
    for h in ["ai", "大模型", "开发", "实习", "实习生", "产品", "运营", "数据", "算法", "后端", "前端"]:
        if h in low and h not in terms:
            terms.append(h)
    return [t for t in terms if len(t) >= 2 or re.fullmatch(r"[a-z+#.]+", t)]


def _alias_in_text(alias: str, normalized_text: str) -> bool:
    alias_low = _norm_for_match(alias)
    if not alias_low:
        return False
    # ASCII aliases should not match inside longer English tokens: Java should
    # not be counted from JavaScript.
    if re.fullmatch(r"[a-z0-9+#.\- ]+", alias_low):
        pattern = r"(?<![a-z0-9])" + re.escape(alias_low).replace(r"\ ", r"\s*") + r"(?![a-z0-9])"
        return re.search(pattern, normalized_text) is not None
    return alias_low in normalized_text


def _norm_for_match(text: Any) -> str:
    return clean_text(text).lower().replace("＋", "+").replace("＃", "#")


def _sort_skills(skills: set[str]) -> list[str]:
    order = {name: i for i, name in enumerate(COMMON_SKILLS)}
    return sorted(skills, key=lambda s: (order.get(s, 999), s.lower()))


def _extract_degree_level(text: str) -> int | None:
    low = _norm_for_match(text)
    found: list[int] = []
    for key, level in DEGREE_LEVELS.items():
        if key in low:
            found.append(level)
    return max(found) if found else None


def _extract_degree_requirement(text: str) -> int | None:
    low = _norm_for_match(text)
    if "学历不限" in low or "不限学历" in low:
        return None
    # In JDs, prefer the lowest explicitly acceptable degree.
    found: list[int] = []
    for key, level in DEGREE_LEVELS.items():
        if key in low:
            found.append(level)
    return min(found) if found else None


def _extract_required_years(text: str) -> int | None:
    low = _norm_for_match(text)
    if re.search(r"经验不限|不限经验|应届|实习", low):
        return None
    range_match = re.search(r"(\d+)\s*[-~—至]\s*(\d+)\s*年", low)
    if range_match:
        return int(range_match.group(1))
    plus_match = re.search(r"(\d+)\s*年\s*(?:以上|及以上|\+)", low)
    if plus_match:
        return int(plus_match.group(1))
    year_match = re.search(r"(\d+)\s*年", low)
    if year_match:
        return int(year_match.group(1))
    return None


def _extract_resume_years(text: str) -> int | None:
    low = _norm_for_match(text)
    explicit = [int(x) for x in re.findall(r"(\d+)\s*年(?:工作|开发|产品|运营|设计|测试|项目|实习)?经验", low)]
    if explicit:
        return max(explicit)
    # Estimate from year ranges in resume, e.g. 2022-2024.
    years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", low)]
    years = [y for y in years if 1990 <= y <= 2035]
    if len(years) >= 2:
        span = max(years) - min(years)
        if 0 <= span <= 20:
            return max(0, span)
    single = re.search(r"(\d+)\s*年", low)
    if single:
        value = int(single.group(1))
        if value <= 20:
            return value
    return None


def _level_and_recommendation(score: float) -> tuple[str, str]:
    if score >= 85:
        return "强匹配", "优先投递；简历只需针对 JD 补充关键词和量化成果。"
    if score >= 75:
        return "推荐投递", "建议投递；投递前把命中技能放到简历摘要和项目首句。"
    if score >= 60:
        return "可投递，需优化", "可以投递；先补齐缺失技能表述和项目量化结果。"
    if score >= 50:
        return "低优先级", "除非岗位很想去，否则优先优化简历或选择更匹配岗位。"
    return "不建议优先", "匹配度偏低，建议换关键词或只作为备选。"


def _enhanced_suggestions(job: JobItem, keyword: str, resume_text: str, max_items: int = 5) -> list[str]:
    suggestions: list[str] = []
    if keyword and _keyword_relevance(keyword, job) < 70:
        suggestions.append(f"岗位与搜索词“{keyword}”相关度一般，先确认岗位标题和职责是否真符合目标方向。")
    if job.missing_skills:
        suggestions.append(f"若已掌握，请在技能栏和项目经历中补充这些 JD 关键词：{'、'.join(job.missing_skills[:6])}。")
    if job.matched_skills:
        suggestions.append(f"把命中技能 {'、'.join(job.matched_skills[:5])} 放到简历摘要或对应项目首句，提高筛选命中率。")
    if not METRIC_PATTERN.search(resume_text):
        suggestions.append("项目/经历中增加量化结果，例如用户量、接口数、转化率、响应时间、成本下降或效率提升。")
    if job.requirement_score < 75:
        suggestions.append("硬性要求存在不确定项，请在简历顶部明确学历、毕业时间、实习/工作年限。")
    if not suggestions:
        suggestions.append("整体匹配较好，投递前按 JD 关键词微调项目描述和成果指标即可。")
    return suggestions[:max_items]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# Optional original backend scoring. It is kept for users who explicitly want to
# compare with the project backend: set JOB_CRAWLER_SCORING_ENGINE=backend.
def _rank_with_backend(resume_text: str, jobs: list[JobItem]) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.services.resume_parse_service import _mock_parse as parse_resume_rule_based
    from app.services.jd_parse_service import _mock_parse_jd as parse_jd_rule_based
    from app.services.scoring_service import compute_scores
    from app.services.diagnosis_service import diagnose

    resume_parsed_model = parse_resume_rule_based(resume_text)
    resume_parsed = _model_to_dict(resume_parsed_model)

    for job in jobs:
        raw_text = job.raw_text()
        jd_parsed_model = parse_jd_rule_based(raw_text, job.title, job.company)
        jd_parsed = _model_to_dict(jd_parsed_model)
        scoring_result = compute_scores(
            resume_parsed=resume_parsed,
            jd_parsed=jd_parsed,
            resume_raw_text=resume_text,
            jd_raw_text=raw_text,
        )
        issues = diagnose(
            resume_parsed=resume_parsed,
            jd_parsed=jd_parsed,
            matched_skills=scoring_result.matched_skills,
            missing_skills=scoring_result.missing_skills,
        )
        detail = scoring_result.score_detail
        job.total_score = scoring_result.total_score
        job.skill_score = detail.skill_score
        job.project_score = detail.project_score
        job.semantic_score = detail.semantic_score
        job.requirement_score = detail.requirement_score
        job.matched_skills = scoring_result.matched_skills
        job.missing_skills = scoring_result.missing_skills
        job.match_level, job.recommendation = _level_and_recommendation(job.total_score)
        job.optimization_suggestions = _suggestions_from_issues(issues)
        job.score_reason = "；".join([
            detail.skill_reason,
            detail.project_reason,
            detail.semantic_reason,
            detail.requirement_reason,
        ])


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    if isinstance(model, dict):
        return model
    raise TypeError(f"无法转换模型类型：{type(model)!r}")


def _suggestions_from_issues(issues: list[Any], max_items: int = 5) -> list[str]:
    out: list[str] = []
    for issue in issues:
        severity = getattr(issue, "severity", "")
        title = getattr(issue, "title", "")
        suggestion = getattr(issue, "suggestion", "")
        item = "：".join(x for x in [title, suggestion] if x)
        if severity:
            item = f"[{severity}] {item}"
        if item and item not in out:
            out.append(item)
        if len(out) >= max_items:
            break
    return out
