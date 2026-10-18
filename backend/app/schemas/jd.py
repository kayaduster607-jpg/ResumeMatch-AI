from typing import Optional

from pydantic import BaseModel, Field


# ── Sub-structures ─────────────────────────────────────

class ParsedJD(BaseModel):
    job_title: str = ""
    company: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    education_requirement: str = ""
    experience_requirement: str = ""
    soft_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    seniority_level: str = ""  # junior / mid / senior / lead
    raw_summary: str = ""


# ── Manual JD request / response ───────────────────────

class JDCreateRequest(BaseModel):
    title: str = ""
    company: str = ""
    raw_text: str


class JDCreateData(BaseModel):
    jd_id: int


class JDCreateResponse(BaseModel):
    success: bool = True
    data: JDCreateData


class JDParseData(BaseModel):
    jd_id: int
    parsed_json: ParsedJD


class JDParseResponse(BaseModel):
    success: bool = True
    data: JDParseData


# ── Recruitment platform search ───────────────────────

class PlatformLoginBrowserRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["all"])


class PlatformLoginStateData(BaseModel):
    message: str = ""
    profile_dir: str = ""
    state_path: str = ""
    opened: list[dict] = Field(default_factory=list)


class PlatformLoginResponse(BaseModel):
    success: bool = True
    data: PlatformLoginStateData


class PlatformSearchRequest(BaseModel):
    keyword: str
    city: str
    platforms: list[str] = Field(default_factory=lambda: ["all"])
    pages: int = 1
    min_score: float = 50.0
    top: int = 50
    strict_city: bool = True
    resume_id: Optional[int] = None
    timeout_ms: int = 60000
    render_wait_ms: int = 5000
    job_type: Optional[str] = None       # 全职 / 实习 / 兼职
    experience: Optional[str] = None     # 应届生 / 1年以下 / 1-3年 / 3-5年 / 5-10年 / 10年以上
    education: Optional[str] = None      # 不限 / 大专 / 本科 / 硕士 / 博士
    district: Optional[str] = None       # 区域，如 天河区 / 南山区
    force_refresh: bool = False          # 强制重新爬取，忽略缓存


class PlatformJobItem(BaseModel):
    id: str
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
    match_level: str = ""
    recommendation: str = ""
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    score_reason: str = ""


class PlatformSearchData(BaseModel):
    keyword: str
    city: str
    platforms: list[str] = Field(default_factory=list)
    total_found: int = 0
    total_after_filter: int = 0
    jobs: list[PlatformJobItem] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    message: str = ""
    from_cache: bool = False  # True when results came from DB cache


class PlatformSearchResponse(BaseModel):
    success: bool = True
    data: PlatformSearchData


class PlatformCollectCurrentRequest(PlatformSearchRequest):
    pass
