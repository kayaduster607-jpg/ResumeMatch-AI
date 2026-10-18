"""Recruitment platform crawler and quick ranking service.

This module intentionally avoids site-specific private APIs where possible.  It
opens each search page in the user's logged-in browser, listens for JSON search
responses, and falls back to DOM card extraction.  The output is normalized so
frontend and analysis code can work with BOSS, Zhaopin, Liepin and 51job in the
same way.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from hashlib import md5
from typing import Any, Optional
from urllib.parse import quote, urljoin

from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.services.skill_normalizer import normalize_skills


PLATFORM_NAMES = {
    "boss": "BOSS直聘",
    "zhaopin": "智联招聘",
    "liepin": "猎聘",
    "qiancheng": "前程无忧",
}

PLATFORM_ALIASES = {
    "all": "all",
    "boss": "boss",
    "boss直聘": "boss",
    "zhipin": "boss",
    "zhaopin": "zhaopin",
    "智联": "zhaopin",
    "智联招聘": "zhaopin",
    "liepin": "liepin",
    "猎聘": "liepin",
    "51job": "qiancheng",
    "qiancheng": "qiancheng",
    "前程无忧": "qiancheng",
}

PLATFORM_LOGIN_URLS = {
    "boss": "https://www.zhipin.com/",
    "zhaopin": "https://passport.zhaopin.com/",
    "liepin": "https://www.liepin.com/",
    "qiancheng": "https://we.51job.com/",
}

# Unified city codes for all platforms.  BOSS/Zhaopin codes come from their public
# city-selector data; Liepin/51job use their own numbering.  For cities beyond the
# initial 17, only Liepin codes are populated (Liepin accepts city name strings as
# fallback), while 51job codes can be left empty — the search URL builder falls back
# to the city name for Liepin and uses the raw string for 51job.
CITY_CODES: dict[str, dict[str, str]] = {
    "北京":   {"boss": "101010100", "zhaopin": "530", "liepin": "010",   "qiancheng": "010000"},
    "上海":   {"boss": "101020100", "zhaopin": "538", "liepin": "020",   "qiancheng": "020000"},
    "广州":   {"boss": "101280100", "zhaopin": "763", "liepin": "050020","qiancheng": "030200"},
    "深圳":   {"boss": "101280600", "zhaopin": "765", "liepin": "050090","qiancheng": "040000"},
    "杭州":   {"boss": "101210100", "zhaopin": "653", "liepin": "070020","qiancheng": "080200"},
    "成都":   {"boss": "101270100", "zhaopin": "801", "liepin": "280020","qiancheng": "090200"},
    "武汉":   {"boss": "101050100", "zhaopin": "736", "liepin": "170020","qiancheng": "180200"},
    "南京":   {"boss": "101180100", "zhaopin": "635", "liepin": "060020","qiancheng": "070200"},
    "苏州":   {"boss": "101190100", "zhaopin": "639", "liepin": "060080","qiancheng": "070300"},
    "西安":   {"boss": "101110100", "zhaopin": "854", "liepin": "270020","qiancheng": "200200"},
    "重庆":   {"boss": "101040100", "zhaopin": "811", "liepin": "040030","qiancheng": "060000"},
    "天津":   {"boss": "101030100", "zhaopin": "531", "liepin": "030",   "qiancheng": "050000"},
    "长沙":   {"boss": "101250100", "zhaopin": "749", "liepin": "180020","qiancheng": "140300"},
    "郑州":   {"boss": "101180100", "zhaopin": "719", "liepin": "150010","qiancheng": "170200"},
    "合肥":   {"boss": "101220100", "zhaopin": "664", "liepin": "150020","qiancheng": "150200"},
    "佛山":   {"boss": "101280800", "zhaopin": "767", "liepin": "050030","qiancheng": "030600"},
    "东莞":   {"boss": "101281600", "zhaopin": "769", "liepin": "050060","qiancheng": "030800"},
    # 省会 & 计划单列市
    "济南":   {"boss": "101120100", "zhaopin": "704", "liepin": "080020","qiancheng": "120400"},
    "青岛":   {"boss": "101120200", "zhaopin": "706", "liepin": "080030","qiancheng": "120300"},
    "厦门":   {"boss": "101230200", "zhaopin": "690", "liepin": "110020","qiancheng": "110300"},
    "福州":   {"boss": "101230100", "zhaopin": "685", "liepin": "110010","qiancheng": "110200"},
    "宁波":   {"boss": "101210400", "zhaopin": "655", "liepin": "070030","qiancheng": "080300"},
    "无锡":   {"boss": "101190200", "zhaopin": "641", "liepin": "070090","qiancheng": "070400"},
    "昆明":   {"boss": "101290100", "zhaopin": "784", "liepin": "250010","qiancheng": "210200"},
    "南宁":   {"boss": "101300100", "zhaopin": "775", "liepin": "230010","qiancheng": "230200"},
    "贵阳":   {"boss": "101260100", "zhaopin": "856", "liepin": "240010","qiancheng": "220200"},
    "南昌":   {"boss": "101240100", "zhaopin": "717", "liepin": "130020","qiancheng": "160200"},
    "太原":   {"boss": "101100100", "zhaopin": "546", "liepin": "090020","qiancheng": "130000"},
    "兰州":   {"boss": "101160100", "zhaopin": "839", "liepin": "260020","qiancheng": "270000"},
    "长春":   {"boss": "101060100", "zhaopin": "613", "liepin": "030020","qiancheng": "080200"},
    "沈阳":   {"boss": "101070100", "zhaopin": "599", "liepin": "080010","qiancheng": "120200"},
    "大连":   {"boss": "101070200", "zhaopin": "600", "liepin": "080040","qiancheng": "120100"},
    "哈尔滨": {"boss": "101050100", "zhaopin": "622", "liepin": "010020","qiancheng": "070200"},
    "海口":   {"boss": "101310100", "zhaopin": "782", "liepin": "210020","qiancheng": "250100"},
    "石家庄": {"boss": "101090100", "zhaopin": "564", "liepin": "050070","qiancheng": "110000"},
    "呼和浩特":{"boss": "101080100","zhaopin": "551", "liepin": "120010","qiancheng": "140000"},
    "乌鲁木齐":{"boss": "101130100","zhaopin": "896", "liepin": "300010","qiancheng": "280000"},
    # 其他常见城市
    "珠海":   {"boss": "101280700", "zhaopin": "771", "liepin": "050050","qiancheng": "030500"},
    "惠州":   {"boss": "101280300", "zhaopin": "773", "liepin": "050070","qiancheng": "040200"},
    "中山":   {"boss": "101281200", "zhaopin": "770", "liepin": "050100","qiancheng": "030700"},
    "常州":   {"boss": "101191000", "zhaopin": "642", "liepin": "070050","qiancheng": "070500"},
    "南通":   {"boss": "101190500", "zhaopin": "647", "liepin": "070060","qiancheng": "080000"},
    "嘉兴":   {"boss": "101210600", "zhaopin": "657", "liepin": "070070","qiancheng": "080500"},
    "温州":   {"boss": "101210800", "zhaopin": "659", "liepin": "070080","qiancheng": "080900"},
    "绍兴":   {"boss": "101210700", "zhaopin": "937", "liepin": "070010","qiancheng": "070600"},
    "徐州":   {"boss": "101190800", "zhaopin": "949", "liepin": "060090","qiancheng": "150200"},
    "烟台":   {"boss": "101120300", "zhaopin": "707", "liepin": "080050","qiancheng": "120500"},
    "威海":   {"boss": "101121300", "zhaopin": "711", "liepin": "080060","qiancheng": "121400"},
    "潍坊":   {"boss": "101120600", "zhaopin": "709", "liepin": "080070","qiancheng": "120700"},
    "洛阳":   {"boss": "101180900", "zhaopin": "720", "liepin": "170030","qiancheng": "170300"},
    "保定":   {"boss": "101090200", "zhaopin": "565", "liepin": "050040","qiancheng": "110200"},
    "三亚":   {"boss": "101310200", "zhaopin": "783", "liepin": "210010","qiancheng": "250200"},
    "拉萨":   {"boss": "101140100", "zhaopin": "889", "liepin": "220010","qiancheng": "260000"},
    "西宁":   {"boss": "101150100", "zhaopin": "880", "liepin": "290010","qiancheng": "290000"},
    "银川":   {"boss": "101170100", "zhaopin": "867", "liepin": "310010","qiancheng": "300000"},
}

BOSS_CITY_CODES = {city: codes["boss"] for city, codes in CITY_CODES.items()}

JOB51_CITY_CODES = {
    "北京": "010000",
    "上海": "020000",
    "广州": "030200",
    "深圳": "040000",
    "杭州": "080200",
    "成都": "090200",
    "武汉": "180200",
    "南京": "070200",
    "苏州": "070300",
    "西安": "200200",
    "重庆": "060000",
    "天津": "050000",
    "长沙": "190200",
    "郑州": "170200",
    "合肥": "150200",
    "佛山": "030600",
    "东莞": "030800",
}

PLATFORM_DOMAINS = {
    "boss": ["zhipin.com"],
    "zhaopin": ["zhaopin.com"],
    "liepin": ["liepin.com"],
    "qiancheng": ["51job.com"],
}

# Response URL keywords that indicate a job search API response.
_PLATFORM_RESPONSE_KEYWORDS = {
    "boss": ("joblist", "job/detail", "zpgeek", "search/job", "wapi/zpgeek"),
    "zhaopin": ("api", "position", "job", "search", "sou", "jobs.zhaopin"),
    "liepin": ("api", "job", "search", "zhaopin", "liepin", "enterprisejob", "recruit/job"),
    "qiancheng": ("api", "job", "search", "joblist", "position", "51job", "search-pc", "job/search"),
}

TECH_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "C++", "C#", "Rust", "PHP", "Ruby",
    "React", "Vue", "Node.js", "FastAPI", "Django", "Flask", "Spring", "Spring Boot", "Express",
    "MySQL", "PostgreSQL", "Redis", "MongoDB", "SQLite", "SQL", "Docker", "Kubernetes", "Elasticsearch",
    "Linux", "Git", "Nginx", "Kafka", "RabbitMQ", "RESTful", "GraphQL", "微服务", "CI/CD", "Jenkins",
    "机器学习", "深度学习", "NLP", "CV", "计算机视觉", "大模型", "LLM", "RAG", "AIGC", "Agent",
    "强化学习", "自然语言处理", "图像处理", "目标检测", "语义分割", "推荐系统", "知识图谱",
    "多模态", "Transformer", "BERT", "GPT", "Stable Diffusion", "生成式AI",
    "PyTorch", "TensorFlow", "Keras", "scikit-learn", "sklearn", "Pandas", "NumPy", "OpenCV",
    "Hugging Face", "LangChain", "向量数据库", "Milvus", "FAISS", "Prompt", "OpenAI",
    "爬虫", "数据分析", "数据挖掘", "数据结构", "算法", "接口", "API", "自动化",
    "前端", "后端", "全栈", "DevOps", "SRE", "云计算", "AWS", "Azure", "华为云", "阿里云",
]

NEGATIVE_KEYWORDS = ["销售", "客服", "电话", "电销", "主播", "运营", "店员", "配送", "保安", "文员"]


@dataclass
class JobItem:
    platform: str
    platform_name: str
    title: str
    company: str = ""
    city: str = ""
    district: str = ""
    address: str = ""
    salary: str = ""
    experience: str = ""
    education: str = ""
    detail_url: str = ""
    raw_text: str = ""
    source: str = ""
    match_score: float = 0.0
    match_level: str = "未评分"
    recommendation: str = ""
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    score_reason: str = ""

    def identity(self) -> str:
        # Prefer the detail URL. When missing, use title+company+city+salt from raw_text
        # so different jobs at different companies are never merged into one.
        if self.detail_url and "zhipin.com/job_detail" in self.detail_url:
            base = f"{self.platform}|{self.detail_url}"
        elif self.detail_url and any(d in self.detail_url for d in ("jobs.zhaopin.com", "jobs.51job.com", "liepin.com")):
            base = f"{self.platform}|{self.detail_url}"
        else:
            raw_salt = (self.raw_text or "")[:80]
            base = f"{self.platform}|{self.title}|{self.company}|{self.city}|{self.salary}|{raw_salt}"
        return md5(base.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.identity(),
            "platform": self.platform,
            "platform_name": self.platform_name,
            "title": self.title,
            "company": self.company,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "salary": self.salary,
            "experience": self.experience,
            "education": self.education,
            "detail_url": self.detail_url,
            "raw_text": self.raw_text,
            "source": self.source,
            "match_score": self.match_score,
            "match_level": self.match_level,
            "recommendation": self.recommendation,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "score_reason": self.score_reason,
        }


# ── Public entry points ───────────────────────────────


def normalize_platforms(platforms: Optional[list[str]]) -> list[str]:
    if not platforms:
        return list(PLATFORM_NAMES.keys())
    normalized: list[str] = []
    for raw in platforms:
        key = PLATFORM_ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())
        if key == "all":
            return list(PLATFORM_NAMES.keys())
        if key in PLATFORM_NAMES and key not in normalized:
            normalized.append(key)
    return normalized or list(PLATFORM_NAMES.keys())



async def crawl_jobs_with_context(context: Any, payload: dict[str, Any]) -> dict[str, Any]:
    keyword = str(payload.get("keyword") or "").strip()
    city = str(payload.get("city") or "").strip()
    platforms = normalize_platforms(payload.get("platforms") or ["all"])
    pages = max(1, min(int(payload.get("pages") or 1), 5))
    top = max(1, min(int(payload.get("top") or 50), 200))
    min_score = float(payload.get("min_score") or 0)
    strict_city = bool(payload.get("strict_city", True))
    render_wait_ms = max(1000, min(int(payload.get("render_wait_ms") or 5000), 30000))
    timeout_ms = max(15000, min(int(payload.get("timeout_ms") or 60000), 120000))
    resume_parsed = payload.get("resume_parsed") or {}
    resume_text = payload.get("resume_text") or ""
    job_type = str(payload.get("job_type") or "").strip() or None
    experience = str(payload.get("experience") or "").strip() or None
    education = str(payload.get("education") or "").strip() or None
    # 区域筛选已移除：只按城市过滤，避免平台区域字段缺失导致误杀。
    district = None

    if not keyword:
        raise RuntimeError("请先填写要搜索的岗位关键词，例如：AI开发实习生 / Python后端 / 产品经理。")
    if not city:
        raise RuntimeError("请先填写目标城市，例如：广州 / 深圳 / 上海。")

    started = time.time()
    errors: list[dict[str, str]] = []
    collected: list[JobItem] = []
    print(f"[search] platforms={platforms}, keyword={keyword!r}, city={city!r}, pages={pages}")

    for platform in platforms:
        try:
            if platform == "boss":
                # BOSS: use direct API crawler to bypass CDP blank-page issue.
                from app.services.boss_api_crawler import crawl_boss_via_api
                jobs = await crawl_boss_via_api(
                    context=context,
                    keyword=keyword,
                    city=city,
                    max_pages=pages,
                )
                # Apply same post-processing as _crawl_one_platform
                jobs = [_enrich_from_raw_text(j) for j in jobs]
                jobs = [_normalize_job_location(j, city) for j in jobs]
                jobs = [_sanitize_job_fields(j, city) for j in jobs]
                pre_city = len(jobs)
                jobs = [j for j in jobs if _city_matches(j, city, strict_city=strict_city)]
                print(f"[boss] city filter: {len(jobs)}/{pre_city}")
                if job_type:
                    pre = len(jobs)
                    jobs = [j for j in jobs if _job_type_matches(j, job_type)]
                    print(f"[boss] job_type={job_type}: {len(jobs)}/{pre}")
                if experience:
                    pre = len(jobs)
                    jobs = [j for j in jobs if _experience_matches(j, experience)]
                    print(f"[boss] experience={experience}: {len(jobs)}/{pre}")
                if education:
                    pre = len(jobs)
                    jobs = [j for j in jobs if _education_matches(j, education)]
                    print(f"[boss] education={education}: {len(jobs)}/{pre}")
                for j in jobs:
                    if city in " ".join([j.city, j.address, j.raw_text]):
                        j.city = city
                    if not j.city:
                        j.city = city
                    j.district = ""
            else:
                jobs = await _crawl_one_platform(
                    context=context,
                    platform=platform,
                    keyword=keyword,
                    city=city,
                    pages=pages,
                    strict_city=strict_city,
                    render_wait_ms=render_wait_ms,
                    timeout_ms=timeout_ms,
                    job_type=job_type,
                    experience=experience,
                    education=education,
                    district=district,
                )
            collected.extend(jobs)
            if not jobs:
                boss_error: dict = {
                    "platform": platform,
                    "platform_name": PLATFORM_NAMES.get(platform, platform),
                    "message": _empty_platform_message(platform),
                }
                try:
                    from app.services.boss_api_crawler import get_bookmarklet_help
                    boss_error["bookmarklet"] = get_bookmarklet_help()
                except Exception:
                    pass
                errors.append(boss_error)
            else:
                print(f"[{platform}] collected {len(jobs)} jobs")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc) or repr(exc)
            print(f"[{platform}] error: {msg[:300]}")
            plat_error: dict = {
                "platform": platform,
                "platform_name": PLATFORM_NAMES.get(platform, platform),
                "message": msg,
            }
            if platform == "boss":
                try:
                    from app.services.boss_api_crawler import get_bookmarklet_help
                    plat_error["bookmarklet"] = get_bookmarklet_help()
                except Exception:
                    pass
            errors.append(plat_error)

    # Close extra BOSS pages after crawling — keep at most one so the browser
    # doesn't stay open with multiple tabs.
    await _cleanup_extra_boss_pages(context)

    deduped = _dedupe_jobs(collected)
    for job in deduped:
        _apply_quick_score(job, keyword=keyword, city=city, resume_parsed=resume_parsed, resume_text=resume_text)

    # 只有匹配分筛选；城市/岗位类型/学历在平台抓取后已做硬条件过滤。
    filtered = [job for job in deduped if job.match_score >= min_score]
    filtered.sort(key=lambda x: (x.match_score, len(x.raw_text or ""), x.company), reverse=True)

    message = f"已抓取 {len(deduped)} 个符合城市和筛选条件的岗位，返回 {len(filtered[:top])} 个。"
    if deduped and not filtered:
        message += f" 最低匹配分 {min_score} 过滤掉了全部候选；请降低最低匹配分或放宽岗位类型/学历条件。"

    return {
        "keyword": keyword,
        "city": city,
        "platforms": platforms,
        "total_found": len(deduped),
        "total_after_filter": len(filtered[:top]),
        "jobs": [job.to_dict() for job in filtered[:top]],
        "all_jobs": [job.to_dict() for job in deduped],  # all deduped jobs before min_score/top filtering
        "errors": errors,
        "elapsed_seconds": round(time.time() - started, 1),
        "message": message,
    }


def _empty_platform_message(platform: str) -> str:
    if platform == "boss":
        return "未抓到岗位。BOSS 如能看到岗位，请不要重新自动搜索，直接点\"采集当前 Edge 页面\"；若空白请在 Edge 里刷新/验证后再采集。也可以使用下方「方法一：书签脚本」手动导出。"
    return "未抓到岗位。已放宽岗位类型后置过滤；请确认该平台已登录，或者先把岗位类型/学历设为\"不限\"。"


async def collect_current_edge_pages(context: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Collect jobs from currently open Edge pages.

    This is the BOSS fallback: the user can manually log in / refresh / search in
    Edge, then click "采集当前 Edge 页面". We parse visible DOM only and do not
    navigate or open new tabs.
    """
    keyword = str(payload.get("keyword") or "").strip()
    city = str(payload.get("city") or "").strip()
    platforms = normalize_platforms(payload.get("platforms") or ["all"])
    top = max(1, min(int(payload.get("top") or 50), 200))
    min_score = float(payload.get("min_score") or 0)
    strict_city = bool(payload.get("strict_city", True))
    resume_parsed = payload.get("resume_parsed") or {}
    resume_text = payload.get("resume_text") or ""
    job_type = str(payload.get("job_type") or "").strip() or None
    experience = str(payload.get("experience") or "").strip() or None
    education = str(payload.get("education") or "").strip() or None

    jobs: list[JobItem] = []
    errors: list[dict[str, str]] = []
    started = time.time()

    try:
        pages = list(getattr(context, "pages", []) or [])
    except Exception:
        pages = []

    for page in pages:
        try:
            url = (getattr(page, "url", "") or "").lower()
            if not url or url == "about:blank":
                continue
            platform = _platform_from_url(url)
            if not platform or platform not in platforms:
                continue
            dom_jobs = await _extract_jobs_from_dom(page, platform)
            if dom_jobs:
                print(f"[current-page] {platform}: dom={len(dom_jobs)} url={url[:100]}")
            jobs.extend(dom_jobs)
        except Exception as exc:
            errors.append({"platform": "current", "platform_name": "当前页面", "message": str(exc)[:200]})

    jobs = _dedupe_jobs(jobs)
    jobs = [_enrich_from_raw_text(job) for job in jobs]
    jobs = [_normalize_job_location(job, city) for job in jobs]
    jobs = [_sanitize_job_fields(job, city) for job in jobs]
    jobs = [j for j in jobs if _city_matches(j, city, strict_city)]
    if job_type:
        jobs = [j for j in jobs if _job_type_matches(j, job_type)]
    if experience:
        jobs = [j for j in jobs if _experience_matches(j, experience)]
    if education:
        jobs = [j for j in jobs if _education_matches(j, education)]
    for job in jobs:
        _apply_quick_score(job, keyword=keyword, city=city, resume_parsed=resume_parsed, resume_text=resume_text)
    jobs = [j for j in jobs if j.match_score >= min_score]
    jobs.sort(key=lambda x: (x.match_score, len(x.raw_text or ""), x.company), reverse=True)

    return {
        "keyword": keyword,
        "city": city,
        "platforms": platforms,
        "total_found": len(jobs),
        "total_after_filter": len(jobs[:top]),
        "jobs": [job.to_dict() for job in jobs[:top]],
        "errors": errors,
        "elapsed_seconds": round(time.time() - started, 1),
        "message": f"已从当前 Edge 页面采集 {len(jobs)} 个符合条件的岗位，返回 {len(jobs[:top])} 个。",
    }


def _platform_from_url(url: str) -> Optional[str]:
    if "zhipin.com" in url:
        return "boss"
    if "zhaopin.com" in url:
        return "zhaopin"
    if "liepin.com" in url:
        return "liepin"
    if "51job.com" in url:
        return "qiancheng"
    return None


def search_platform_jobs(payload: dict[str, Any], db: Optional[Session] = None) -> dict[str, Any]:
    """API-facing search function. Loads resume text when resume_id is present.

    Caches crawled results in DB keyed by (keyword, city, platforms, pages, job_type,
    experience, education).  Subsequent identical searches return the cached data after
    re-scoring with the current resume.  Pass force_refresh=True to skip the cache.
    """
    keyword = str(payload.get("keyword") or "").strip()
    city = str(payload.get("city") or "").strip()
    platforms = normalize_platforms(payload.get("platforms") or ["all"])
    pages = max(1, min(int(payload.get("pages") or 1), 5))
    job_type = str(payload.get("job_type") or "").strip() or None
    experience = str(payload.get("experience") or "").strip() or None
    education = str(payload.get("education") or "").strip() or None
    force_refresh = bool(payload.get("force_refresh", False))

    resume_parsed = {}
    resume_text = ""
    if db is not None and payload.get("resume_id"):
        try:
            resume = db.get(Resume, int(payload["resume_id"]))
        except AttributeError:
            resume = db.query(Resume).filter(Resume.id == int(payload["resume_id"])).first()
        if resume is not None:
            resume_text = resume.raw_text or ""
            if resume.parsed_json:
                try:
                    resume_parsed = json.loads(resume.parsed_json)
                except Exception:
                    resume_parsed = {}

    # Build cache key and check for existing cache
    platforms_sorted = sorted(platforms)
    cache_key = json.dumps([keyword, city, platforms_sorted, pages, job_type or "", experience or "", education or ""], ensure_ascii=False)

    if db is not None and not force_refresh:
        from app.models.cached_job_search import CachedJobSearch
        from datetime import datetime

        cached = (
            db.query(CachedJobSearch)
            .filter(
                CachedJobSearch.keyword == keyword,
                CachedJobSearch.city == city,
                CachedJobSearch.platforms_json == json.dumps(platforms_sorted, ensure_ascii=False),
                CachedJobSearch.pages == pages,
                CachedJobSearch.job_type == job_type,
                CachedJobSearch.experience == experience,
                CachedJobSearch.education == education,
            )
            .order_by(CachedJobSearch.created_at.desc())
            .first()
        )

        if cached is not None:
            print(f"[cache] hit for {keyword!r} {city!r}, age={datetime.utcnow() - cached.created_at}")

            try:
                cached_jobs = json.loads(cached.jobs_json)
                cached_errors = json.loads(cached.errors_json)
            except Exception:
                cached_jobs = []
                cached_errors = []

            # Re-build JobItem list and re-score with current resume
            jobs: list[JobItem] = []
            for jd in cached_jobs:
                job = JobItem(
                    platform=jd.get("platform", ""),
                    platform_name=jd.get("platform_name", ""),
                    title=jd.get("title", ""),
                    company=jd.get("company", ""),
                    city=jd.get("city", ""),
                    district=jd.get("district", ""),
                    address=jd.get("address", ""),
                    salary=jd.get("salary", ""),
                    experience=jd.get("experience", ""),
                    education=jd.get("education", ""),
                    detail_url=jd.get("detail_url", ""),
                    raw_text=jd.get("raw_text", ""),
                    source=jd.get("source", ""),
                )
                jobs.append(job)

            # Re-score with current resume (which may have changed since cache)
            for job in jobs:
                _apply_quick_score(
                    job,
                    keyword=keyword,
                    city=city,
                    resume_parsed=resume_parsed,
                    resume_text=resume_text,
                )

            min_score = float(payload.get("min_score") or 0)
            top = max(1, min(int(payload.get("top") or 50), 200))
            filtered = [j for j in jobs if j.match_score >= min_score]
            filtered.sort(key=lambda x: (x.match_score, len(x.raw_text or ""), x.company), reverse=True)

            message = f"已从缓存加载 {len(jobs)} 个符合条件的岗位，返回 {len(filtered[:top])} 个（缓存时间：{cached.created_at.strftime('%m-%d %H:%M')}）。"
            if jobs and not filtered:
                message += f" 最低匹配分 {min_score} 过滤掉了全部候选；请降低最低匹配分。"

            return {
                "keyword": keyword,
                "city": city,
                "platforms": platforms,
                "total_found": len(jobs),
                "total_after_filter": len(filtered[:top]),
                "jobs": [job.to_dict() for job in filtered[:top]],
                "errors": cached_errors,
                "elapsed_seconds": cached.elapsed_seconds,
                "message": message,
                "from_cache": True,
            }

    # Cache miss or force refresh — do the actual crawl
    from app.services.playwright_browser_worker import get_browser_worker

    payload["resume_text"] = resume_text
    payload["resume_parsed"] = resume_parsed
    result = get_browser_worker().search_jobs(payload)

    # Save to cache (store all deduped jobs, not just the filtered top)
    all_jobs_data = result.get("all_jobs") or result.get("jobs") or []
    if db is not None and all_jobs_data:
        from app.models.cached_job_search import CachedJobSearch

        try:
            # Upsert: delete old cache for same key, insert new
            db.query(CachedJobSearch).filter(
                CachedJobSearch.keyword == keyword,
                CachedJobSearch.city == city,
                CachedJobSearch.platforms_json == json.dumps(platforms_sorted, ensure_ascii=False),
                CachedJobSearch.pages == pages,
                CachedJobSearch.job_type == job_type,
                CachedJobSearch.experience == experience,
                CachedJobSearch.education == education,
            ).delete()

            cache_entry = CachedJobSearch(
                keyword=keyword,
                city=city,
                platforms_json=json.dumps(platforms_sorted, ensure_ascii=False),
                pages=pages,
                job_type=job_type,
                experience=experience,
                education=education,
                total_found=result.get("total_found", 0),
                total_after_filter=result.get("total_after_filter", 0),
                jobs_json=json.dumps(all_jobs_data, ensure_ascii=False),
                errors_json=json.dumps(result.get("errors", []), ensure_ascii=False),
                elapsed_seconds=result.get("elapsed_seconds", 0),
                message=result.get("message", ""),
            )
            db.add(cache_entry)
            db.commit()
            print(f"[cache] saved {len(all_jobs_data)} jobs for {keyword!r} {city!r}")
        except Exception as exc:
            print(f"[cache] save error: {exc}")
            try:
                db.rollback()
            except Exception:
                pass

    # Don't leak the internal all_jobs key to API responses
    result.pop("all_jobs", None)
    return result


async def _crawl_one_platform(
    context: Any,
    platform: str,
    keyword: str,
    city: str,
    pages: int,
    strict_city: bool,
    render_wait_ms: int,
    timeout_ms: int,
    job_type: str = None,
    experience: str = None,
    education: str = None,
    district: str = None,
) -> list[JobItem]:
    all_jobs: list[JobItem] = []
    total_captured = 0

    for page_no in range(1, pages + 1):
        page = None
        api_jobs: list[JobItem] = []
        dom_jobs: list[JobItem] = []
        captured_urls: list[str] = []
        parse_errors: list[str] = []
        response_tasks: list[asyncio.Task] = []

        async def handle_response(response: Any) -> None:
            try:
                url = (getattr(response, "url", "") or "").lower()
                if not _should_capture_response(platform, url, getattr(response, "headers", None)):
                    return
                captured_urls.append(url[:180])
                status = getattr(response, "status", 0)
                data = None
                try:
                    data = await response.json()
                except Exception:
                    try:
                        body = await response.text()
                        data = _parse_json_from_body(body)
                    except Exception:
                        data = None
                if data is None:
                    parse_errors.append(f"JSON解析失败(status={status}): {url[:100]}")
                    return
                extracted = _extract_jobs_from_json(data, platform, response.url)
                if extracted:
                    api_jobs.extend(extracted)
                    print(f"[{platform}] response extracted {len(extracted)} jobs from {url[:100]}")
                elif platform in ("liepin", "qiancheng"):
                    # Log first few captured URLs for debugging
                    print(f"[{platform}] response captured but 0 jobs from {url[:120]}, status={status}")
            except Exception as exc:  # noqa: BLE001
                parse_errors.append(f"响应处理异常: {str(exc)[:120]}")

        def on_response(response: Any) -> None:
            try:
                response_tasks.append(asyncio.create_task(handle_response(response)))
            except RuntimeError:
                pass

        try:
            context.on("response", on_response)
        except Exception:
            pass

        # Search tabs are closed after extraction.  For BOSS blank/verification pages
        # we keep the real zhipin tab open so the user can refresh/verify and then
        # click "采集当前 Edge 页面". Pure about:blank tabs are still cleaned up.
        keep_page_open = False
        try:
            url = _build_search_url(
                platform,
                keyword,
                city,
                page_no,
                job_type=job_type,
                experience=experience,
                education=education,
                district=district,
            )
            print(f"[{platform}] goto {url[:160]}")
            page = await _open_platform_page(context, platform, url, timeout_ms)

            # Wait + scroll to trigger lazy loaded cards and API responses.
            try:
                await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15000))
            except Exception:
                pass
            await _progressive_scroll(page, platform=platform, render_wait_ms=render_wait_ms)

            if response_tasks:
                await asyncio.gather(*response_tasks, return_exceptions=True)

            try:
                dom_jobs.extend(await _extract_jobs_from_dom(page, platform))
            except Exception as dom_exc:
                print(f"[{platform}] DOM extract warning: {str(dom_exc)[:120]}")

            if platform == "boss" and not api_jobs and not dom_jobs:
                # If the newly-opened BOSS tab is blank, there may still be an
                # older manually refreshed BOSS tab with real cards.  Try all
                # current BOSS pages before reporting failure.
                fallback_jobs = await _extract_existing_platform_pages(context, platform, exclude_page=page)
                if fallback_jobs:
                    dom_jobs.extend(fallback_jobs)
                    print(f"[boss] fallback existing pages dom={len(fallback_jobs)}")
                else:
                    state = await _inspect_boss_page_state(page)
                    try:
                        purl = (getattr(page, "url", "") or "").lower()
                    except Exception:
                        purl = ""
                    # Keep a real BOSS page open for manual refresh/verification,
                    # but do not keep meaningless about:blank tabs.
                    keep_page_open = "zhipin.com" in purl and "about:blank" not in purl
                    try:
                        await page.bring_to_front()
                    except Exception:
                        pass
                    raise RuntimeError(state)
        finally:
            try:
                context.off("response", on_response)
            except Exception:
                pass
            # Keep search tabs open during multi-platform crawl so the user
            # can see results.  Blank about:blank tabs are still cleaned up.
            if page is not None and not keep_page_open:
                # Don't close BOSS pages to avoid flashing; close others after a short delay
                if platform == "boss":
                    pass  # Keep BOSS tab open
                else:
                    try:
                        await asyncio.sleep(0.5)
                        await page.close()
                    except Exception:
                        pass

        merged = _dedupe_jobs(api_jobs + dom_jobs)
        total_captured += len(captured_urls)
        all_jobs.extend(merged)
        print(
            f"[{platform}] page {page_no}: captured={len(captured_urls)}, "
            f"api={len(api_jobs)}, dom={len(dom_jobs)}, merged={len(merged)}"
        )

    print(f"[{platform}] total before post-process: {len(all_jobs)}, api responses={total_captured}")
    all_jobs = _dedupe_jobs(all_jobs)
    all_jobs = [_enrich_from_raw_text(job) for job in all_jobs]
    all_jobs = [_normalize_job_location(job, city) for job in all_jobs]
    all_jobs = [_sanitize_job_fields(job, city) for job in all_jobs]

    pre_city = len(all_jobs)
    all_jobs = [job for job in all_jobs if _city_matches(job, city, strict_city=strict_city)]
    print(f"[{platform}] city filter: {len(all_jobs)}/{pre_city}")

    if job_type:
        pre = len(all_jobs)
        all_jobs = [j for j in all_jobs if _job_type_matches(j, job_type)]
        print(f"[{platform}] job_type={job_type}: {len(all_jobs)}/{pre}")
    if experience:
        pre = len(all_jobs)
        all_jobs = [j for j in all_jobs if _experience_matches(j, experience)]
        print(f"[{platform}] experience={experience}: {len(all_jobs)}/{pre}")
    if education:
        pre = len(all_jobs)
        all_jobs = [j for j in all_jobs if _education_matches(j, education)]
        print(f"[{platform}] education={education}: {len(all_jobs)}/{pre}")
    # district intentionally ignored.

    # Final display cleanup: UI should only show the city, not district.
    for job in all_jobs:
        if city in " ".join([job.city, job.address, job.raw_text]):
            job.city = city
        if not job.city:
            job.city = city
        job.district = ""

    return all_jobs


async def _extract_existing_platform_pages(context: Any, platform: str, exclude_page: Any = None) -> list[JobItem]:
    """Parse already-open pages for one platform without navigation.

    This is mainly for BOSS: a DevTools-opened search tab may be blank, while a
    manually refreshed BOSS tab in the same managed Edge window already contains
    visible cards.
    """
    jobs: list[JobItem] = []
    try:
        pages = list(getattr(context, "pages", []) or [])
    except Exception:
        return jobs
    for p in pages:
        if exclude_page is not None and p is exclude_page:
            continue
        try:
            url = (getattr(p, "url", "") or "").lower()
            if not url or "about:blank" in url:
                continue
            if _platform_from_url(url) != platform:
                continue
            extracted = await _extract_jobs_from_dom(p, platform)
            if extracted:
                jobs.extend(extracted)
        except Exception:
            continue
    return _dedupe_jobs(jobs)


async def _open_platform_page(context: Any, platform: str, url: str, timeout_ms: int) -> Any:
    """Open a platform page.

    For all platforms, prefer CDP new_page + goto.  Only fall back to the Edge
    system-command path when CDP navigation clearly produces a blank page after retry.
    This avoids the visual flashing caused by launching a separate Edge process for
    each BOSS tab.
    """
    # Try CDP navigation first for all platforms (simpler, no flashing).
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=min(timeout_ms, 30000))
    except Exception as nav_exc:
        print(f"[{platform}] navigation warning: {str(nav_exc)[:180]}")
    try:
        await page.bring_to_front()
    except Exception:
        pass

    # For BOSS, verify the page is not blank; retry once via reload if it is.
    if platform == "boss":
        blank = await _is_page_blank(page)
        if blank:
            print(f"[boss] first navigation gave blank page, reloading...")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass
            blank2 = await _is_page_blank(page)
            if blank2:
                print(f"[boss] still blank after reload, trying fallback via Edge command")
                try:
                    await page.close()
                except Exception:
                    pass
                return await _open_boss_via_edge_command(context, url, timeout_ms)

    return page


async def _is_page_blank(page: Any) -> bool:
    """Return True if the page has no visible content."""
    try:
        body = await page.locator("body").inner_text(timeout=3000)
        title = await page.title()
        return (not (body or "").strip()) and (not (title or "").strip())
    except Exception:
        return False


async def _open_boss_via_edge_command(context: Any, url: str, timeout_ms: int) -> Any:
    """Fallback: open BOSS URL by asking the real Edge process to handle it."""
    from app.services.playwright_browser_worker import open_url_in_managed_edge
    before_ids = {id(p) for p in list(getattr(context, "pages", []) or [])}
    open_url_in_managed_edge(url, prefer_system_command=True)
    deadline = time.time() + min(max(timeout_ms / 1000, 15), 35)
    while time.time() < deadline:
        pages = list(getattr(context, "pages", []) or [])
        for p in reversed(pages):
            try:
                purl = (getattr(p, "url", "") or "").lower()
            except Exception:
                continue
            if "zhipin.com" not in purl:
                continue
            if id(p) not in before_ids:
                try:
                    await p.bring_to_front()
                except Exception:
                    pass
                try:
                    await p.wait_for_timeout(2000)
                except Exception:
                    pass
                return p
        await asyncio.sleep(0.35)
    raise RuntimeError("BOSS Edge command fallback: 未能通过Edge命令打开BOSS页面")


async def _progressive_scroll(page: Any, platform: str, render_wait_ms: int) -> None:
    # BOSS needs gentle scrolls to trigger lazy load without visual flicker.
    rounds = 6 if platform == "boss" else 3
    pause = max(400, min(1500, render_wait_ms // 3))
    try:
        await page.wait_for_timeout(max(1000, min(render_wait_ms, 4000)))
    except Exception:
        pass
    for _ in range(rounds):
        try:
            await page.evaluate("() => window.scrollBy({top: 600, behavior: 'smooth'})")
        except Exception:
            try:
                await page.mouse.wheel(0, 600)
            except Exception:
                pass
        try:
            await page.wait_for_timeout(pause)
        except Exception:
            pass


async def _patch_boss_blank_page(page: Any, target_url: str) -> None:
    """Retry a blank BOSS page in-place instead of opening extra blank tabs."""
    try:
        await page.wait_for_timeout(1500)
        body = await page.locator("body").inner_text(timeout=3000)
        title = await page.title()
        if (not body.strip()) and (not title.strip()):
            try:
                await page.reload(wait_until="domcontentloaded", timeout=20_000)
                await page.wait_for_timeout(1800)
            except Exception:
                pass
            try:
                body2 = await page.locator("body").inner_text(timeout=2000)
                title2 = await page.title()
                if (not body2.strip()) and (not title2.strip()):
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
                    await page.wait_for_timeout(2000)
            except Exception:
                pass
    except Exception:
        pass


async def _cleanup_extra_boss_pages(context: Any) -> None:
    """Close extra BOSS pages keeping at most one, so the browser doesn't stay open."""
    try:
        pages = list(getattr(context, "pages", []) or [])
    except Exception:
        return
    boss_pages = []
    for p in pages:
        try:
            url = (getattr(p, "url", "") or "").lower()
            if "zhipin.com" in url and "about:blank" not in url:
                boss_pages.append(p)
        except Exception:
            continue
    # Close all but the last BOSS page
    for p in boss_pages[:-1]:
        try:
            await p.close()
        except Exception:
            pass


async def _inspect_boss_page_state(page: Any) -> str:
    try:
        url = (page.url or "").lower()
        title = await page.title()
        body = await page.locator("body").inner_text(timeout=5000)
    except Exception:
        return "BOSS 未抓到岗位，且无法读取页面状态。请点\"打开浏览器登录\"确认 BOSS 已登录，再点\"采集当前 Edge 页面\"。"

    body_preview = (body or "").strip()[:300]
    if not body_preview and not (title or "").strip():
        return "BOSS 页面为空白。已尽量保留真实 BOSS 标签页；请在 Edge 里手动刷新/完成验证，然后点\"采集当前 Edge 页面\"。"
    if "安全验证" in body or "滑动验证" in body or "请完成验证" in body or "环境存在异常" in body:
        return "BOSS 需要安全验证或检测到异常环境。请点\"打开浏览器登录\"进入 BOSS，完成验证后再搜索。"
    if any(kw in body for kw in ["登录", "注册", "手机号", "微信登录", "扫码登录"]):
        return "BOSS 当前未登录或登录态失效。请点\"打开浏览器登录\"进入 BOSS 登录后重试。"
    return f"BOSS 未抓到岗位。页面标题：{title or '空'}；URL：{url[:120]}；页面文本预览：{body_preview}"


def _build_search_url(platform: str, keyword: str, city: str, page: int,
                      job_type: str = None, experience: str = None,
                      education: str = None, district: str = None) -> str:
    """Build broad city+keyword URLs.

    We deliberately do NOT push jobType/education filters into platform URLs.
    The mapping is inconsistent across BOSS/Zhaopin/Liepin/51job and previously
    caused every platform to filter to zero.  Local post-filters below now apply
    strict user-selected conditions, including dropping cards whose selected fields are missing.
    """
    from urllib.parse import urlencode
    kw = keyword.strip()
    city_codes = CITY_CODES.get(city, {})
    city_code = city_codes.get(platform, "")
    if platform == "boss":
        return "https://www.zhipin.com/web/geek/job?" + urlencode({"query": kw, "city": city_code or "101280600", "page": str(page)})
    if platform == "zhaopin":
        return "https://sou.zhaopin.com/?" + urlencode({"pageSize": "30", "cityId": city_code or "765", "kw": kw, "kt": "3", "pageIndex": str(page - 1)})
    if platform == "liepin":
        return "https://www.liepin.com/zhaopin/?" + urlencode({"key": kw, "dq": city_code or city, "currentPage": str(page - 1), "pageSize": "40"})
    if platform == "qiancheng":
        return "https://we.51job.com/pc/search?" + urlencode({"jobArea": city_code or "040000", "keyword": kw, "searchType": "1", "page": str(page), "pageSize": "20"})
    raise RuntimeError(f"不支持的平台：{platform}")


def _should_capture_response(platform: str, url: str, headers: Any = None) -> bool:
    """Check if a response URL looks like a real job search/detail API."""
    domains = PLATFORM_DOMAINS.get(platform, [])
    if not any(domain in url for domain in domains):
        return False
    if platform == "boss":
        blocked = (
            "expect/list", "recommend/expect", "user/expect", "geek/expect",
            "security", "captcha", "friend", "chat", "city/site", "filter/conditions",
        )
        if any(b in url for b in blocked):
            return False
        positive = ("joblist", "job/list", "search/job", "job/detail", "job/detail.json", "zpgeek/search")
        if any(k in url for k in positive):
            return True
        if headers:
            try:
                ct = (headers.get("content-type", "") or "").lower()
                return "json" in ct and "job" in url
            except Exception:
                return False
        return False
    keywords = _PLATFORM_RESPONSE_KEYWORDS.get(platform, [])
    if any(k in url for k in keywords):
        return True
    if headers:
        try:
            ct = (headers.get("content-type", "") or "").lower()
            if "json" in ct and any(k in url for k in ("job", "position", "search", "list")):
                return True
        except Exception:
            pass
    return False


def _parse_json_from_body(text: str) -> Any:
    """Try to extract JSON from page body text."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return None


# Keep old function for backward compatibility
def _looks_like_job_response(url: str) -> bool:
    keywords = [
        "job", "jobs", "position", "positions", "search", "zpgeek", "zhaopin",
        "liepin", "51job", "list", "recommend", "zpapi", "api",
    ]
    return any(k in url for k in keywords)


# ── JSON extraction ───────────────────────────────────


def _extract_jobs_from_json(data: Any, platform: str, source_url: str) -> list[JobItem]:
    """Extract jobs from JSON response, using known paths first, then recursive search."""
    if data is None:
        return []

    job_dicts: list[dict[str, Any]] = []

    # Fast paths for known response shapes (BOSS, Zhaopin, etc.)
    if isinstance(data, dict):
        known_paths = [
            # BOSS
            "zpData.jobList",
            "zpData.jobInfo",
            "data.jobList",
            "data.jobCardList",
            "data.list",
            "data.items",
            "data.results",
            "data.data.list",
            "data.pageData.jobList",
            "data.resultData.jobList",
            "data.entity.jobList",
            "resultbody.job.items",
            "resultbody.items",
            "searchResult.list",
            # 猎聘 / 前程无忧 additional paths
            "data.data",
            "data.result",
            "data.records",
            "data.content",
            "data.jobList",
            "result.data",
            "result.data.list",
            "result.data.items",
            "result.data.records",
            "result.data.jobCardList",
            "data.body.jobList",
            "data.body.list",
            "data.body.items",
            "data.jobSearchResult.jobList",
            "data.searchResult.jobItems",
            "data.searchResult.items",
            "body.jobList",
            "body.jobs",
            "body.list",
            # 猎聘 real jobCardList
            "data.data.jobCardList",
            "data.jobCardList",
            "jobCardList",
        ]
        for path in known_paths:
            val = _get_path_value(data, path)
            if isinstance(val, list):
                job_dicts.extend(x for x in val if isinstance(x, dict))
            elif isinstance(val, dict) and path not in ("data", "zpData", "result", "body"):
                job_dicts.append(val)

    # Fallback: recursive search
    if not job_dicts:
        job_dicts = _walk_candidate_dicts(data)

    if platform in ("boss", "liepin", "qiancheng") and job_dicts:
        print(f"[{platform}] _extract_jobs_from_json: {len(job_dicts)} dicts to process")
        if job_dicts:
            sample = job_dicts[0]
            all_keys = list(sample.keys())
            print(f"[{platform}] First dict keys ({len(all_keys)}): {all_keys}")
            if platform == "boss":
                print(f"[boss] First dict sample: jobName={sample.get('jobName')}, brandName={sample.get('brandName')}, salaryDesc={sample.get('salaryDesc')}, cityName={sample.get('cityName')}, encryptJobId={sample.get('encryptJobId')}")
            else:
                # Print all key-value pairs for first 3 dicts to debug 猎聘/前程无忧
                for k, v in sample.items():
                    val_preview = str(v)[:120] if v is not None else "None"
                    print(f"[{platform}]   {k}: {val_preview}")
            if "jobInfo" in sample:
                ji = sample["jobInfo"]
                if isinstance(ji, dict):
                    print(f"[{platform}] Nested jobInfo keys: {list(ji.keys())[:20]}")
            for k in ("postDescription", "description", "jobDesc", "content"):
                v = sample.get(k)
                if v and isinstance(v, str) and len(v) > 10:
                    print(f"[{platform}] Found '{k}' ({len(v)} chars): {v[:100]}...")

    # Log when walk_candidate_dicts found something but known_paths didn't
    if platform in ("liepin", "qiancheng") and job_dicts:
        print(f"[{platform}] total candidate dicts after walk: {len(job_dicts)}")
    elif platform in ("liepin", "qiancheng") and not job_dicts:
        print(f"[{platform}] No candidate job dicts found in response")

    jobs: list[JobItem] = []
    none_count = 0
    for item in job_dicts:
        job = _dict_to_job(item, platform, source_url)
        if job:
            jobs.append(job)
        else:
            none_count += 1

    if platform == "boss" and job_dicts:
        print(f"[boss] _dict_to_job: {len(jobs)} jobs, {none_count} None")

    return _dedupe_jobs(jobs)


def _get_path_value(obj: Any, path: str) -> Any:
    """Get value from nested dict using dot-separated path."""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _walk_candidate_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if _looks_like_job_dict(node):
                found.append(node)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return found


def _looks_like_job_dict(d: dict[str, Any]) -> bool:
    keys = {str(k).lower() for k in d.keys()}
    title_keys = {
        "jobname", "jobtitle", "positionname", "title", "position", "job_name",
        "positiontitle", "jobtitlename", "recruitname", "postname",
    }
    company_keys = {
        "companyname", "company", "brandname", "compname", "company_name",
        "comname", "brand", "hiringorganization", "corpname", "enterprisename", "entname",
    }
    salary_keys = {
        "salary", "salarydesc", "jobsalary", "providesalarystring", "salary60",
        "salarystring", "salarytext", "compensation", "pay", "salartrang",
    }
    city_keys = {
        "cityname", "city", "workcity", "dq", "jobarea", "locationname",
        "area", "location", "worklocation", "jobcity",
    }
    id_keys = {
        "encryptjobid", "jobid", "job_id", "positionid", "jobnumber", "number",
        "id", "recruitid", "jobcode",
    }
    has_title = bool(keys & title_keys)
    if not has_title:
        for subkey in ("position", "job", "jobInfo", "recruitInfo"):
            sub = d.get(subkey)
            if isinstance(sub, dict) and any(k in {str(x).lower() for x in sub.keys()} for k in title_keys):
                has_title = True
                break
    signal_groups = [company_keys, salary_keys, city_keys, id_keys]
    signal_count = sum(1 for group in signal_groups if keys & group)
    return has_title and signal_count >= 2


def _dict_to_job(d: dict[str, Any], platform: str, source_url: str) -> Optional[JobItem]:
    # 前程无忧 / 猎聘 often nest job fields inside jobListItemVO / job / comp sub-objects.
    # Promote their fields so the existing pickers can find them.
    for container_key in ("jobListItemVO", "jobInfo", "job", "comp", "recruitInfo"):
        inner = d.get(container_key)
        if isinstance(inner, dict):
            d = {**d}  # shallow copy to avoid mutating the original
            for sub_k, sub_v in inner.items():
                if sub_k not in d:
                    d[sub_k] = sub_v

    title = _pick_str(d, [
        "jobName", "jobTitle", "positionName", "title", "name", "position", "job_name", "positionTitle",
        "jobname", "jobtitle", "positionname", "jobTitleName",
    ])
    if not title:
        title = _pick_nested(d, ["position.name", "job.name", "jobInfo.jobName", "jobInfo.title",
                                  "jobListItemVO.jobName", "jobListItemVO.title",
                                  "comp.jobName", "comp.title"])
    if not title or len(title) > 120:
        if platform in ("boss", "liepin", "qiancheng") and d:
            print(f"[{platform}] _dict_to_job: no title. keys={list(d.keys())[:15]}")
        return None

    company = _pick_str(d, [
        "companyName", "company", "brandName", "compName", "company_name", "comName", "brand", "hiringOrganization",
        "companyname", "corpName", "corpname", "enterpriseName", "entName",
    ])
    if not company:
        company = _pick_nested(d, ["company.name", "brand.name", "hiringOrganization.name", "corp.name",
                                    "comp.compName", "comp.name", "comp.companyName",
                                    "jobListItemVO.companyName", "jobListItemVO.companyname"])
    if platform == "boss" and not company:
        return None
    # 猎聘/前程无忧 允许没有公司字段，从 raw text 里后补
    city = _pick_str(d, [
        "cityName", "workCity", "city", "jobAreaString", "jobArea", "locationName", "city_name",
        "dq", "area", "location", "workLocation", "jobCity", "cityNameStr",
    ])
    if not city:
        city = _pick_nested(d, ["city.display", "jobLocation.address.addressLocality", "workLocation.city",
                                  "workLocation.display", "workLocation.name",
                                  "jobListItemVO.jobAreaString", "jobListItemVO.cityName",
                                  "comp.city", "comp.workLocation"])
    district = _pick_str(d, [
        "district", "districtName", "areaDistrict", "businessDistrict", "area",
        "jobAreaLevelDetail", "dqDesc", "county", "town",
    ])
    address = _pick_str(d, [
        "address", "workAddress", "jobAddress", "location", "businessDistrict",
        "workLocationStr", "jobLocationStr",
    ])
    salary = _pick_str(d, [
        "salaryDesc", "salary", "jobSalary", "provideSalaryString", "salary60",
        "salaryString", "salaryText", "salaryRange", "compensation", "pay",
    ])
    if not salary:
        salary = _pick_nested(d, ["jobListItemVO.provideSalaryString", "jobListItemVO.salary",
                                    "comp.salary", "comp.salaryDesc"])
    experience = _pick_str(d, [
        "experienceName", "workYear", "workingExp", "experience", "jobYear",
        "requireWorkYears", "workExperience", "workYearString", "yearRequired",
    ])
    if not experience:
        experience = _pick_nested(d, ["jobListItemVO.workYearString", "jobListItemVO.requireWorkYears",
                                        "comp.workYear", "comp.experience"])
    education = _pick_str(d, [
        "degreeName", "education", "eduLevel", "jobDegree", "requireEduLevel",
        "degree", "eduRequirement",
    ])
    if not education:
        education = _pick_nested(d, ["jobListItemVO.degreeString", "jobListItemVO.eduLevel",
                                       "comp.degree", "comp.education"])
    detail_url = _pick_url(d, platform, source_url)
    desc = _pick_str(d, [
        "jobDesc", "description", "jobDescription", "content", "postDescription",
        "responsibility", "jobDetail", "positionDesc", "jobContent", "duty",
    ])
    if not desc:
        desc = _pick_nested(d, ["jobListItemVO.jobDesc", "jobListItemVO.description",
                                  "comp.description", "comp.jobDesc"])
    tags = _pick_list_str(d, [
        "skills", "skillLabels", "jobLabels", "welfareList", "labels", "tags",
        "tagList", "skillLabel", "benefits",
    ])

    raw_parts = [title, company, city, district, address, salary, experience, education, desc, " ".join(tags)]
    raw_text = "\n".join([p for p in raw_parts if p])

    return JobItem(
        platform=platform,
        platform_name=PLATFORM_NAMES[platform],
        title=_clean(title),
        company=_clean(company),
        city=_clean(city),
        district=_clean(district),
        address=_clean(address),
        salary=_clean(salary),
        experience=_clean(experience),
        education=_clean(education),
        detail_url=detail_url,
        raw_text=_clean_multiline(raw_text),
        source="api",
    )


def _pick_nested(d: dict[str, Any], paths: list[str]) -> str:
    """Pick a value from nested dict using dot-separated paths like 'company.name'."""
    for path in paths:
        cur = d
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                cur = None
                break
        if cur is not None:
            if isinstance(cur, str) and cur.strip():
                return cur.strip()
            if isinstance(cur, (int, float)):
                return str(cur)
            if isinstance(cur, dict):
                for subkey in ("name", "display", "value", "text", "label"):
                    if subkey in cur and cur[subkey]:
                        return str(cur[subkey])
    return ""


def _pick_str(d: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key in d and d[key] is not None:
            value = d[key]
            if isinstance(value, (str, int, float)):
                return str(value)
            if isinstance(value, dict):
                # Common nested name pattern.
                for subkey in ["name", "value", "text", "label"]:
                    if subkey in value and value[subkey] is not None:
                        return str(value[subkey])
            if isinstance(value, list):
                joined = " ".join(str(x.get("name", x)) if isinstance(x, dict) else str(x) for x in value[:5])
                if joined.strip():
                    return joined
    return ""


def _pick_list_str(d: dict[str, Any], keys: list[str]) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = d.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    text = _pick_str(item, ["name", "label", "value", "text"])
                else:
                    text = str(item)
                if text:
                    values.append(text)
    return values


def _pick_url(d: dict[str, Any], platform: str, source_url: str) -> str:
    raw = _pick_str(d, ["detailUrl", "jobUrl", "url", "href", "link", "positionURL", "redirectUrl"])
    if not raw:
        raw = _pick_nested(d, ["jobListItemVO.detailUrl", "jobListItemVO.jobUrl",
                                 "comp.detailUrl", "comp.jobUrl"])
    if raw:
        return urljoin(_platform_base_url(platform), raw)

    # Construct best-effort detail URLs for common IDs.
    job_id = _pick_str(d, ["encryptJobId", "jobId", "positionId", "id", "jobid"])
    lid = _pick_str(d, ["lid", "securityId"])
    if platform == "boss" and job_id:
        suffix = f"?lid={quote(lid)}" if lid else ""
        return f"https://www.zhipin.com/job_detail/{job_id}.html{suffix}"
    return source_url


def _platform_base_url(platform: str) -> str:
    return {
        "boss": "https://www.zhipin.com/",
        "zhaopin": "https://www.zhaopin.com/",
        "liepin": "https://www.liepin.com/",
        "qiancheng": "https://we.51job.com/",
    }[platform]


# ── DOM extraction ────────────────────────────────────


async def _extract_jobs_from_dom(page: Any, platform: str) -> list[JobItem]:
    """Extract job cards from DOM and visible text.

    BOSS and Zhaopin change class names frequently.  The visible card text is
    more stable, so this extractor combines CSS selectors, job-detail links and a
    line-based fallback.
    """
    script = r"""
    (platform) => {
      const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
      const abs = (href) => {
        if (!href) return '';
        try { return new URL(href, location.href).href; } catch { return href; }
      };
      const platformSelectors = {
        boss: [
          '.job-card-wrapper', '.job-card-wrap', '.job-card-box', '.job-card-left', '.job-card-body',
          '.search-job-result .job-card-wrapper', '.search-job-result .job-card-box',
          '[ka="search_list_job"]', '[class*="job-card"]', '[class*="JobCard"]', 'a[href*="/job_detail/"]'
        ],
        zhaopin: ['.joblist-box__item', '[class*="joblist"] [class*="item"]', '[class*="position"] [class*="item"]', '[class*="job-card"]', 'a[href*="jobs.zhaopin.com"]'],
        liepin: [
          '.job-card-left', '.job-card-box', '.job-list-item', '.job-list-box > div',
          '[class*="job-card"]', '[class*="job-list"] [class*="item"]', '[class*="job-list-item"]',
          '[class*="position-card"]', '[class*="recruit-card"]', 'li[class*="job"]',
          'a[href*="/lptjob/"]', 'a[href*="/job/"]', '.left-list-box > div',
        ],
        qiancheng: [
          '.joblist-item', '.joblist-box .job-item', '.j_joblist > div',
          '.joblist-item-box', '.joblist [class*="item"]', '[class*="job-item"]',
          '[class*="j_joblist"] [class*="item"]', '[class*="position-item"]',
          'a[href*="jobs.51job.com"]', '.e-job-list > li', '.e_ji',
        ]
      };
      let rawNodes = [];
      for (const sel of (platformSelectors[platform] || [])) {
        for (const n of Array.from(document.querySelectorAll(sel))) rawNodes.push(n);
      }
      for (const a of Array.from(document.querySelectorAll('a[href*="job_detail"],a[href*="jobdetail"],a[href*="/lptjob/"],a[href*="jobs.zhaopin.com"],a[href*="jobs.51job.com"]'))) {
        rawNodes.push(a.closest('.job-card-wrapper,.job-card-box,.job-card-left,li,[class*="job-card"],[class*="item"]') || a);
      }
      const nodes = [];
      const nodeSeen = new Set();
      for (const n of rawNodes) {
        if (!n || nodeSeen.has(n)) continue;
        nodeSeen.add(n);
        nodes.push(n);
      }
      const titleSelectors = ['[class*="job-name"]','[class*="jobName"]','[class*="job-title"]','[class*="position-name"]','[class*="positionName"]','.job-title','.name','h3','h2','a'];
      const compSelectors = ['[class*="company-name"]','[class*="companyName"]','[class*="company"]','[class*="comp-name"]','[class*="brand"]','.cname','.company'];
      const salSelectors = ['[class*="salary"]','[class*="sal"]','[class*="money"]','[class*="pay"]'];
      const areaSelectors = ['[class*="job-area"]','[class*="city"]','[class*="area"]','[class*="location"]','[class*="addr"]'];
      const findText = (card, selectors, maxLen) => {
        for (const sel of selectors) {
          const el = card.querySelector(sel);
          const t = clean(el?.innerText || el?.textContent || '');
          if (t && (!maxLen || t.length <= maxLen)) return t;
        }
        return '';
      };
      const salaryRe = /\d+\s*[-~]\s*\d+\s*(?:元\/天|元\/月|元\/年|k|K|千|万|万\/年|万\/月)|\d+\s*[kK](?:\s*[-~]\s*\d+\s*[kK])?|面议/;
      const titleRe = /AI|算法|开发|工程师|实习|产品|测试|后端|前端|数据|机器学习|大模型|Agent|NLP|LLM|硬件|软件|运维|架构|分析|助理/i;
      const companyRe = /公司|科技|信息|网络|软件|集团|有限|股份|智能|数据|研究院|学院|大学|银行|咨询|服务|华为|腾讯|阿里|安全|公共/;
      const jobs = [];
      const seen = new Set();
      for (const card of nodes) {
        if (jobs.length >= 80) break;
        const raw = card.innerText || card.textContent || '';
        const text = clean(raw);
        if (text.length < 16) continue;
        const lines = raw.split(/\n+/).map(clean).filter(Boolean);
        let title = findText(card, titleSelectors, 80);
        title = clean(title.split(/\s{2,}|\|/)[0]);
        if (!title || title.length > 80 || salaryRe.test(title) || /登录|注册|筛选|推荐|地图|搜索|求职期望|清空|收藏|立即沟通/.test(title)) {
          title = '';
          for (const line of lines.slice(0, 8)) {
            if (line.length <= 80 && !salaryRe.test(line) && titleRe.test(line) && !/登录|注册|筛选|搜索|地图|收藏|沟通/.test(line)) { title = line; break; }
          }
        }
        if (!title || title.length < 2 || title.length > 100) continue;
        let company = findText(card, compSelectors, 100);
        let salary = findText(card, salSelectors, 60);
        let city = findText(card, areaSelectors, 60);
        if (!salary) salary = (text.match(salaryRe) || [''])[0];
        if (!company || company.length > 100 || company === title || salaryRe.test(company)) {
          company = '';
          for (const line of lines) {
            if (line !== title && companyRe.test(line) && !salaryRe.test(line) && line.length <= 90) { company = line; break; }
          }
        }
        if (!city || city.length > 60) {
          const m = text.match(/(北京|上海|广州|深圳|杭州|成都|武汉|南京|苏州|西安|重庆|天津|长沙|郑州|合肥|佛山|东莞)(?:[·\-\s][\u4e00-\u9fa5A-Za-z0-9]+)?/);
          city = m ? m[0] : '';
        }
        const linkEl = card.querySelector('a[href*="job"],a[href*="position"],a[href*="detail"],a[href*="zhaopin"],a[href*="liepin"],a[href*="51job"]') || (card.tagName === 'A' ? card : null);
        const href = linkEl ? abs(linkEl.href || linkEl.getAttribute('href')) : '';
        const key = [platform, title, company, salary, href].join('|');
        if (seen.has(key)) continue;
        seen.add(key);
        jobs.push({ jobName: title, companyName: company, salary, cityName: city, url: href, description: text.slice(0, 2000) });
      }
      return { jobs, bodyText: document.body ? document.body.innerText : '', url: location.href, title: document.title };
    }
    """
    try:
        result = await page.evaluate(script, platform)
    except Exception:
        result = {"jobs": [], "bodyText": ""}

    jobs: list[JobItem] = []
    for card in (result or {}).get("jobs", []) or []:
        title = _clean(card.get("jobName", ""))
        if not title or len(title) < 2:
            continue
        company = _clean(card.get("companyName", ""))
        salary = _clean(card.get("salary", ""))
        city_name = _clean(card.get("cityName", ""))
        detail_url = _clean(card.get("url", ""))
        desc = _clean(card.get("description", ""))
        raw_parts = [title, company, city_name, salary, desc]
        jobs.append(JobItem(
            platform=platform,
            platform_name=PLATFORM_NAMES.get(platform, platform),
            title=title,
            company=company,
            city=city_name,
            salary=salary,
            detail_url=detail_url,
            raw_text=_clean_multiline("\n".join([p for p in raw_parts if p])),
            source="dom",
        ))

    body_text = ((result or {}).get("bodyText") or "")
    if body_text:
        jobs.extend(_extract_jobs_from_visible_text(body_text, platform))
    return _dedupe_jobs(jobs)


def _extract_jobs_from_visible_text(text: str, platform: str) -> list[JobItem]:
    lines = [_clean(x) for x in (text or "").splitlines() if _clean(x)]
    if not lines:
        return []
    jobs: list[JobItem] = []
    salary_re = re.compile(r"\d+\s*[-~]\s*\d+\s*(?:元/天|元/月|元/年|k|K|千|万|万/月|万/年)|\d+\s*[kK](?:\s*[-~]\s*\d+\s*[kK])?|面议")
    title_re = re.compile(r"AI|算法|开发|工程师|实习|产品|测试|后端|前端|数据|机器学习|大模型|Agent|NLP|LLM|硬件|软件|运维|架构|分析|助理", re.I)
    company_re = re.compile(r"公司|科技|信息|网络|软件|集团|有限|股份|智能|数据|研究院|学院|大学|银行|咨询|服务|华为|腾讯|阿里|字节|美团|京东|安全|公共")
    city_re = re.compile(r"(北京|上海|广州|深圳|杭州|成都|武汉|南京|苏州|西安|重庆|天津|长沙|郑州|合肥|佛山|东莞)(?:[·\-\s][一-龥A-Za-z0-9]+)?")
    for i, line in enumerate(lines):
        sal_match = salary_re.search(line)
        if not sal_match:
            continue
        title = line[:sal_match.start()].strip(" -·|，,")
        if not title or len(title) < 2 or not title_re.search(title):
            for j in range(max(0, i - 3), i + 1):
                cand = salary_re.sub("", lines[j]).strip(" -·|，,")
                if 2 <= len(cand) <= 80 and title_re.search(cand) and not re.search(r"搜索|筛选|登录|注册|地图|收藏|沟通", cand):
                    title = cand
                    break
        if not title or len(title) > 100 or not title_re.search(title):
            continue
        block_text = "\n".join(lines[max(0, i - 2): i + 10])
        salary = sal_match.group(0).strip()
        company = ""
        for cand in lines[i:i + 8]:
            if cand == title or salary in cand:
                continue
            if company_re.search(cand) and len(cand) <= 90:
                company = cand
                break
        city = ""
        m = city_re.search(block_text)
        if m:
            city = m.group(0)
        exp = ""
        edu = ""
        m_exp = re.search(r"(经验不限|不限经验|应届|在校|\d+\s*[-~]\s*\d+\s*年|\d+\s*年以[上下]|\d+\s*个月|\d+天/周)", block_text)
        if m_exp:
            exp = m_exp.group(1)
        m_edu = re.search(r"(学历不限|不限学历|大专|本科|硕士|博士)", block_text)
        if m_edu:
            edu = m_edu.group(1)
        jobs.append(JobItem(
            platform=platform,
            platform_name=PLATFORM_NAMES.get(platform, platform),
            title=_clean_job_title(title),
            company=_clean_company_name(company, title),
            city=city,
            salary=salary,
            experience=exp,
            education=edu,
            raw_text=_clean_multiline(block_text[:1500]),
            source="text",
        ))
    return _dedupe_jobs(jobs)


def _card_text_to_job(text: str, href: str, platform: str) -> Optional[JobItem]:
    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    if not lines:
        return None

    salary = ""
    for line in lines:
        if re.search(r"\d+\s*[kK千万]|\d+\s*-\s*\d+|薪", line):
            salary = line
            break

    title = lines[0]
    # If first line is salary or a platform label, choose a more title-like line.
    for line in lines[:6]:
        if line == salary:
            continue
        if len(line) <= 60 and not re.search(r"登录|注册|筛选|推荐|薪资", line):
            title = line
            break

    company = ""
    for line in lines[1:8]:
        if line == salary or line == title:
            continue
        if re.search(r"公司|科技|信息|网络|软件|集团|有限|股份|教育|咨询|电商|智能|数据", line):
            company = line
            break

    city = ""
    district = ""
    for line in lines[:12]:
        loc = _extract_location_from_text(line)
        if loc:
            city, district = loc
            break

    exp = ""
    edu = ""
    for line in lines[:12]:
        if not exp and re.search(r"经验|[0-9]+年|应届|不限", line):
            exp = line
        if not edu and re.search(r"本科|大专|硕士|博士|学历", line):
            edu = line

    if not title or len(title) > 100:
        return None

    return JobItem(
        platform=platform,
        platform_name=PLATFORM_NAMES[platform],
        title=title,
        company=company,
        city=city,
        district=district,
        salary=salary,
        experience=exp,
        education=edu,
        detail_url=href or "",
        raw_text=_clean_multiline(text),
        source="dom",
    )


# ── City filtering ────────────────────────────────────



def _job_type_matches(job: JobItem, job_type: str) -> bool:
    """Apply the user-selected job type as a real filter.

    Earlier versions kept unknown cards, so selecting "实习" still returned
    director/full-time roles.  Here we keep a card only when it has a positive
    signal for the selected type, or when the selected type is 不限.
    """
    if not job_type or job_type == "不限":
        return True

    title = job.title or ""
    salary = job.salary or ""
    exp = job.experience or ""
    raw = job.raw_text or ""
    text = " ".join([title, salary, exp, raw]).lower()

    internship_positive = ["实习", "intern", "internship", "校招", "校园招聘", "在校", "应届", "元/天", "天/周", "个月"]
    part_positive = ["兼职", "part-time", "part time", "日结", "小时工"]
    fulltime_negative = ["全职", "社招", "正式员工", "10年", "5-10年", "3-5年", "总监", "负责人", "leader", "经理", "主管"]

    if job_type == "实习":
        if any(k in text for k in internship_positive):
            return True
        # Strong non-internship signals must be removed.
        if any(k.lower() in text for k in fulltime_negative):
            return False
        # Monthly/annual salary without internship signal is usually not intern.
        if re.search(r"\d+\s*[-~]\s*\d+\s*(k|K|万/月|万/年|千/月)", salary + " " + raw):
            return False
        return False

    if job_type == "兼职":
        if any(k in text for k in part_positive):
            return True
        if any(k in text for k in ["全职", "实习", "校招", "社招", "正式员工"]):
            return False
        return False

    if job_type == "全职":
        if any(k in text for k in internship_positive + part_positive):
            return False
        return True

    return True


def _experience_matches(job: JobItem, experience: str) -> bool:
    """Drop only clearly incompatible experience levels.

    Experience options from the UI are Chinese labels.  Unknown cards are kept
    only for broad selections; for explicit junior/intern selections we filter
    out senior roles.
    """
    if not experience or experience == "不限":
        return True
    text = " ".join([job.title or "", job.experience or "", job.raw_text or ""])

    if experience in ("应届", "在校/应届"):
        if any(k in text for k in ["应届", "在校", "校招", "实习", "经验不限", "不限经验"]):
            return True
        if re.search(r"[1-9]\d*\s*[-~]\s*[1-9]\d*\s*年|[1-9]\d*\s*年以[上下]|3-5年|5-10年|10年", text):
            return False
        return False

    # Normalize selected experience into max allowed years.
    max_year = None
    if "1" in experience and ("以内" in experience or "以下" in experience or "1年" in experience):
        max_year = 1
    elif "3" in experience:
        max_year = 3
    elif "5" in experience:
        max_year = 5
    elif "10" in experience:
        max_year = 10

    if max_year is None:
        return True

    if any(k in text for k in ["经验不限", "不限经验", "应届", "在校", "实习"]):
        return True
    years = []
    for m in re.finditer(r"(\d+)\s*[-~]\s*(\d+)\s*年", text):
        years.append(int(m.group(2)))
    for m in re.finditer(r"(\d+)\s*年以[上下]", text):
        years.append(int(m.group(1)))
    if not years:
        # 用户明确选择经验条件时，卡片没有任何经验字段就不保留，避免筛选看起来失效。
        return False
    return min(years) <= max_year


def _education_matches(job: JobItem, education: str) -> bool:
    """Apply selected education requirement.

    If the user selects 本科, keep 本科/大专/学历不限, drop 硕士/博士.
    Unknown education is NOT kept, because the user explicitly complained that filters looked ignored.
    """
    if not education or education == "不限":
        return True
    text = " ".join([job.education or "", job.raw_text or ""])
    edu_order = {"高中": 0, "中专": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}
    user_level = edu_order.get(education, 0)
    if user_level == 0 and education not in edu_order:
        return True
    if "学历不限" in text or "不限学历" in text:
        return True
    found = [name for name in ["博士", "硕士", "本科", "大专", "中专", "高中"] if name in text]
    if not found:
        # 用户明确选择学历条件时，卡片没有学历字段就不保留，避免筛选看起来失效。
        return False
    required = max(edu_order.get(x, 0) for x in found)
    return user_level >= required

def _enrich_from_raw_text(job: JobItem) -> JobItem:
    """Extract company/salary/experience/education from raw_text when structured fields are empty."""
    text = job.raw_text
    if not text:
        return job

    # Company: search full text for company name pattern
    if not job.company:
        # Match: Chinese chars (no digits/spaces) + company suffix
        # Use word boundary: company name should be preceded by space/start and followed by space
        _company_suffix = r'(?:科技|信息|网络|软件|集团|股份|研究院|大学|学院|公司|银行|证券|保险|物流|贸易|能源|机械|电子|通信|半导体|芯片|汽车|地产|医疗|生物|制造|传媒|新材料|新能源|智能|数据|教育|咨询|电商|资本|投资|食品|农业|环保|化工|建筑|装饰)'
        # Find all matches and pick the shortest reasonable one (most likely a company name)
        candidates = []
        for m in re.finditer(r'(?:^|[\s【])([一-龥A-Za-z]{2,20}' + _company_suffix + r')', text):
            name = m.group(1).strip()
            if len(name) >= 4 and name != job.title and not any(c in name for c in "01234567890 "):
                candidates.append(name)
        if candidates:
            # Pick shortest candidate (most likely a clean company name)
            job.company = min(candidates, key=len)

    # Salary: find number range + unit anywhere in text
    if not job.salary:
        m = re.search(r'(\d+\s*[-~]\s*\d+\s*(?:元/天|元/月|元/年|[kK万/月千]))', text)
        if m:
            job.salary = m.group(1).strip()
        else:
            m = re.search(r'(\d+\s*[kK]\s*[xX×]\s*\d+)', text)
            if m:
                job.salary = m.group(1).strip()

    # Experience: find experience pattern
    if not job.experience:
        m = re.search(r'(应届|[1-9]\d*\s*[-~]\s*[1-9]\d*\s*年|[1-9]\d*\s*年以[上下]|经验不限|不限经验)', text)
        if m:
            job.experience = m.group(1).strip()

    # Education: find degree keyword
    if not job.education:
        m = re.search(r'(本科|大专|硕士|博士|学历不限|不限学历)', text)
        if m:
            job.education = m.group(1).strip()

    return job


def _normalize_job_location(job: JobItem, target_city: str) -> JobItem:
    text = " ".join([job.city, job.district, job.address, job.raw_text])
    known_cities = list(CITY_CODES.keys())

    # Only rewrite city → target when NO other known city appears in the text.
    other_cities = [c for c in known_cities if c in text and c != target_city]
    if target_city in text and not other_cities:
        job.city = target_city
        return job

    if not job.city:
        loc = _extract_location_from_text(" ".join([job.address, job.raw_text]))
        if loc:
            job.city, job.district = loc
            return job

    # If a platform card only shows district (e.g. 南山区) while the search URL
    # is already city-restricted, display the requested city instead of the district.
    if job.city and not any(city in job.city for city in CITY_CODES.keys()):
        if re.search(r"[一-龥]{2,}(区|县|镇|街道)$", job.city):
            # Only rewrite to target if no other city in raw text
            if not other_cities:
                job.district = job.city
                job.city = target_city
    return job


def _extract_location_from_text(text: str) -> Optional[tuple[str, str]]:
    """Extract (city, district) from text.

    First tries known cities from CITY_CODES, then falls back to a generic
    pattern that matches any "XX市" or "XX·YY" (city·district) format, so
    even cities not in the known list are recognised and can be filtered out.
    """
    # 1 – known-cities list
    cities = sorted(CITY_CODES.keys(), key=len, reverse=True)
    for city in cities:
        if city not in text:
            continue
        idx = text.find(city)
        after = text[idx + len(city) : idx + len(city) + 30].strip()
        district = ""
        m = re.match(r'^[\s\-\—\–\【\（\(\:：·]*([一-龥]{2,}(?:区|县|市|镇|街))', after)
        if m:
            district = m.group(1)
        elif re.match(r'^[\s\-\—\–\【\（\(\:：·]*([一-龥]{2,})', after):
            m2 = re.match(r'^[\s\-\—\–\【\（\(\:：·]*([一-龥]{2,10})', after)
            if m2:
                district = m2.group(1)
        return city, district

    # 2 – generic pattern: "XX市" anywhere in the text
    m = re.search(r'([一-龥]{2,4})市', text)
    if m:
        city = m.group(1)
        after = text[m.end():m.end() + 30].strip()
        district = ""
        dm = re.match(r'^[\s\-\—\–\·]*([一-龥]{2,}(?:区|县|镇|街))', after)
        if dm:
            district = dm.group(1)
        return city, district

    # 3 – "XX·YY" pattern (city·district) — common on zhaopin/51job
    m = re.search(r'([一-龥]{2,4})\s*·\s*([一-龥]{2,}(?:区|县|镇|街道|园|开发区))', text)
    if m:
        city = m.group(1)
        district = m.group(2).strip()
        return city, district

    return None


def _city_matches(job: JobItem, target_city: str, strict_city: bool) -> bool:
    """City-only filter.

    Uses the generic _extract_location_from_text helper which recognises both
    known cities from CITY_CODES and unknown cities via XX市/XX·YY patterns.
    """
    if not strict_city:
        return True

    # Build combined text from all location-bearing fields.
    location_text = " ".join([job.city or "", job.address or ""]).strip()
    raw_text = job.raw_text or ""
    all_text = " ".join([location_text, raw_text])

    if target_city in all_text:
        return True

    # Extract the city from structured location first, then from raw text.
    loc = _extract_location_from_text(location_text) if location_text else None
    if not loc:
        loc = _extract_location_from_text(raw_text)

    if loc:
        found_city, _ = loc
        if found_city == target_city:
            return True
        # If we can identify a specific other city, reject.
        return False

    # District-only cards (e.g. "南山区") are allowed — the search URL is
    # already city-constrained.  But verify no other known city appears in
    # the combined text.
    compact_location = re.sub(r"\s+", "", location_text)
    if compact_location:
        # Check compact_location itself against CITY_CODES
        known_cities = list(CITY_CODES.keys())
        for city in known_cities:
            if city in compact_location and city != target_city:
                return False
        # Also check raw_text for other cities
        for city in known_cities:
            if city in raw_text and city != target_city:
                return False
        # District-like short names are OK
        if re.search(r"[一-龥]{1,12}(区|县|镇|街道|园区|开发区|新区|高新区)$", compact_location):
            return True
        if 1 <= len(compact_location) <= 8 and re.fullmatch(r"[一-龥A-Za-z0-9·]+", compact_location):
            # Last safety check: compact_location itself doesn't look like a city name
            generic_city = re.search(r'([一-龥]{2,4})市', compact_location)
            if generic_city:
                city_name = generic_city.group(1)
                if city_name != target_city:
                    return False
            return True

    # No location info at all — keep (search URL is city-constrained).
    return True


def _sanitize_job_fields(job: JobItem, target_city: str) -> JobItem:
    """Clean noisy card fields so UI/JD import do not treat whole card as company.

    Important: never blindly rewrite a district/county into the target city before
    city filtering. Doing that turns 北京朝阳/成都高新 into 深圳 and lets wrong-city
    jobs leak through. If the city field is only a district, keep it as district
    and let _city_matches inspect raw_text for explicit other cities.
    """
    job.title = _clean_job_title(job.title)
    job.company = _clean_company_name(job.company, job.title)
    if job.city:
        loc = _extract_location_from_text(job.city)
        if loc:
            job.city = loc[0]
            job.district = loc[1]
        elif target_city in " ".join([job.city, job.address, job.raw_text or ""]):
            job.district = job.city if re.search(r"[一-龥]{2,}(区|县|镇|街道)$", job.city) else job.district
            job.city = target_city
        elif re.search(r"[一-龥]{2,}(区|县|镇|街道)$", job.city):
            job.district = job.city
            job.city = ""
    # UI只展示城市；区县不作为筛选条件。
    job.district = ""
    return job


def _clean_job_title(title: str) -> str:
    title = _clean(title)
    if not title:
        return ""
    # Common card title noise: "AI工程师 【 深圳 】 30-45k ..."
    title = re.split(r"\s*[【\[]", title, maxsplit=1)[0].strip()
    title = re.split(r"\s+\d+\s*[-~]", title, maxsplit=1)[0].strip()
    return title[:80]


def _clean_company_name(company: str, title: str = "") -> str:
    text = _clean(company)
    if not text:
        return ""
    title = _clean(title)
    # If the whole job card was mistakenly captured as company, extract a likely company phrase.
    suffix = r"(?:有限公司|股份有限公司|上市公司|公司|集团|科技|信息|网络|软件|智能|数据|研究院|学院|大学|银行|证券|保险|医疗|生物|制造|传媒|资本|投资|电商|咨询)"
    candidates = []
    for m in re.finditer(r"([一-龥A-Za-z0-9·（）()]{2,35}" + suffix + r")", text):
        cand = _clean(m.group(1))
        if cand and cand != title and not re.search(r"\d+\s*[-~]\s*\d+", cand):
            candidates.append(cand)
    if candidates:
        # Pick the shortest meaningful candidate, usually the clean company name.
        return min(candidates, key=len)[:80]

    # Otherwise split by visible separators and discard job/salary/location fragments.
    parts = re.split(r"[\n|·•,，;；]+|\s{2,}", text)
    for part in parts:
        part = _clean(part)
        if not part or part == title:
            continue
        if len(part) > 50:
            continue
        if re.search(r"\d+\s*[-~]\s*\d+|年|学历|在线|顾问|招聘|职位|岗位", part):
            continue
        return part[:80]

    if len(text) > 80 or (title and title in text):
        return ""
    return text[:80]


# ── Quick scoring ─────────────────────────────────────


def _apply_quick_score(job: JobItem, keyword: str, city: str, resume_parsed: dict[str, Any], resume_text: str) -> None:
    text = " ".join([job.title, job.company, job.city, job.district, job.salary, job.experience, job.education, job.raw_text])
    text_lower = text.lower()

    has_resume = bool((resume_text or "").strip() or resume_parsed)
    resume_skills = _extract_resume_skills(resume_parsed, resume_text) if has_resume else []
    job_skills = _extract_skills_from_text(text)
    matched = sorted(set(resume_skills) & set(job_skills))
    missing = sorted(set(job_skills) - set(resume_skills))[:12]

    keyword_tokens = _keyword_tokens(keyword)
    title_relevance = _keyword_relevance(job.title + " " + job.raw_text, keyword_tokens)
    if not job_skills:
        skill_score = 70.0
    elif not has_resume:
        skill_score = 65.0
    else:
        skill_score = (len(matched) / max(len(job_skills), 1)) * 100
    city_score = 100.0 if city in text else 70.0
    info_score = min(100.0, 45.0 + len(job.raw_text) / 8.0)

    # Experience/education fields are not always present in cards, so do not
    # punish too hard when missing.
    completeness_score = 60.0
    if job.salary:
        completeness_score += 15
    if job.experience:
        completeness_score += 10
    if job.education:
        completeness_score += 10
    completeness_score = min(100.0, completeness_score)

    score = (
        title_relevance * 0.34
        + skill_score * 0.36
        + city_score * 0.12
        + info_score * 0.10
        + completeness_score * 0.08
    )

    # Strong cap for clearly irrelevant roles: user searching AI/dev should not
    # see sales/customer-service roles with a random high score.
    if title_relevance < 35:
        score = min(score, 49.0)
    if any(word in job.title for word in NEGATIVE_KEYWORDS) and not any(word in keyword for word in NEGATIVE_KEYWORDS):
        score = min(score, 45.0)

    job.match_score = round(max(0.0, min(100.0, score)), 1)
    job.match_level, job.recommendation = _score_level(job.match_score)
    job.matched_skills = matched[:20]
    job.missing_skills = missing
    job.score_reason = (
        f"岗位相关度 {title_relevance:.0f}，"
        f"技能命中 {len(matched)}/{len(job_skills) or 0}{'（未上传简历，技能分按中性处理）' if not has_resume else ''}，"
        f"城市匹配 {'是' if city in text else '未明确'}。"
    )


def _extract_resume_skills(resume_parsed: dict[str, Any], resume_text: str) -> list[str]:
    raw: list[str] = []
    if resume_parsed:
        raw.extend(resume_parsed.get("skills") or [])
        for proj in resume_parsed.get("projects") or []:
            raw.extend(proj.get("tech_stack") or [])
        for exp in resume_parsed.get("work_experience") or []:
            raw.extend(_extract_skills_from_text(" ".join([exp.get("title", ""), exp.get("description", ""), " ".join(exp.get("achievements") or [])])))
    raw.extend(_extract_skills_from_text(resume_text or ""))
    return sorted({s.name for s in normalize_skills(raw) if s.name})


def _extract_skills_from_text(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for skill in TECH_KEYWORDS:
        skill_lower = skill.lower()
        # Use word boundary matching for short skills to avoid false positives
        if len(skill_lower) <= 2:
            # For short skills like "C#", "Go", "R" — require word boundary
            pattern = r'(?<![a-zA-Z])' + re.escape(skill_lower) + r'(?![a-zA-Z])'
            if re.search(pattern, lower) or skill in text:
                found.append(skill)
        else:
            if skill_lower in lower or skill in text:
                found.append(skill)
    # Normalize so aliases like sklearn/Golang are comparable.
    return sorted({s.name for s in normalize_skills(found) if s.name and len(s.name) >= 2})


def _keyword_tokens(keyword: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]+", keyword.lower())
    cn = re.findall(r"[\u4e00-\u9fff]{2,}", keyword)
    tokens = words + cn
    # Add useful sub-tokens for Chinese job keywords.
    for part in ["AI", "开发", "后端", "前端", "产品", "运营", "实习", "算法", "数据", "爬虫", "大模型", "机器学习"]:
        if part.lower() in keyword.lower() or part in keyword:
            tokens.append(part.lower())
    return sorted(set(t for t in tokens if t))


def _keyword_relevance(text: str, tokens: list[str]) -> float:
    if not tokens:
        return 70.0
    lower = text.lower()
    hits = 0
    for token in tokens:
        token_l = token.lower()
        if token_l in lower or token in text:
            hits += 1
    ratio = hits / len(tokens)
    if ratio >= 1:
        return 100.0
    if ratio >= 0.66:
        return 85.0
    if ratio >= 0.34:
        return 68.0
    return 25.0


def _score_level(score: float) -> tuple[str, str]:
    if score >= 85:
        return "强匹配", "优先投递，并针对缺失技能微调简历。"
    if score >= 75:
        return "推荐投递", "值得投递，建议补充岗位关键词。"
    if score >= 60:
        return "可投递，需优化", "可以投，但应先强化项目描述和技能呈现。"
    if score >= 50:
        return "低优先级", "不建议优先投递，除非岗位很感兴趣。"
    return "不建议优先", "岗位关键词或技能差异较大，建议跳过。"


# ── Utilities ─────────────────────────────────────────


def _dedupe_jobs(jobs: list[JobItem]) -> list[JobItem]:
    """Deduplicate jobs while preserving same-title jobs at different companies."""
    best: dict[str, JobItem] = {}
    for job in jobs:
        if not job.title:
            continue
        key = job.identity()
        if key not in best:
            best[key] = job
        else:
            existing = best[key]
            # Always merge missing fields from the new entry
            _merge_job_fields(existing, job)
            # Keep the entry with the best data score
            if _job_data_score(job) > _job_data_score(existing):
                _merge_job_fields(job, existing)
                best[key] = job
    return list(best.values())


def _merge_job_fields(target: JobItem, source: JobItem) -> None:
    """Merge non-empty fields from source into target."""
    if not target.company and source.company:
        target.company = source.company
    if not target.salary and source.salary:
        target.salary = source.salary
    if not target.city and source.city:
        target.city = source.city
    if not target.detail_url and source.detail_url:
        target.detail_url = source.detail_url
    if not target.experience and source.experience:
        target.experience = source.experience
    if not target.education and source.education:
        target.education = source.education
    if not target.district and source.district:
        target.district = source.district
    if source.raw_text and len(source.raw_text) > len(target.raw_text or ""):
        target.raw_text = source.raw_text


def _job_data_score(job: JobItem) -> int:
    """Score how much data a job item has (higher = more complete)."""
    score = 0
    if job.company:
        score += 3
    if job.salary:
        score += 2
    if job.detail_url:
        score += 2
    if job.experience:
        score += 1
    if job.education:
        score += 1
    if job.raw_text and len(job.raw_text) > 50:
        score += 1
    return score


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_multiline(value: str) -> str:
    lines = [_clean(line) for line in str(value or "").splitlines()]
    return "\n".join([line for line in lines if line])
