from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
import re


def clean_text(value: Any, max_len: int | None = None) -> str:
    """Normalize text extracted from JSON/DOM."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        value = "、".join(clean_text(v) for v in value if clean_text(v))
    text = str(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace(" ", " ")
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.strip()
    if max_len and len(text) > max_len:
        return text[:max_len].rstrip()
    return text


def normalize_city_name(city: str) -> str:
    city = clean_text(city).lower()
    city = city.replace("市", "")
    city = re.sub(r"[\s,，/|·\-]+", "", city)
    return city


@dataclass
class JobItem:
    platform: str
    platform_name: str = ""
    job_id: str = ""
    security_id: str = ""
    title: str = ""
    company: str = ""
    salary: str = ""
    city: str = ""
    district: str = ""
    experience: str = ""
    degree: str = ""
    skills: list[str] = field(default_factory=list)
    description: str = ""
    url: str = ""
    source_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    # ranking / analysis fields, populated later
    total_score: float = 0.0
    skill_score: float = 0.0
    project_score: float = 0.0
    semantic_score: float = 0.0
    requirement_score: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    optimization_suggestions: list[str] = field(default_factory=list)
    score_reason: str = ""
    match_level: str = ""
    recommendation: str = ""

    def key(self) -> str:
        if self.platform and self.job_id:
            return f"{self.platform}:{self.job_id}"
        if self.platform and self.url:
            return f"{self.platform}:url:{self.url}"
        return f"{self.platform}:{self.title}:{self.company}:{self.city}:{self.salary}".lower()

    def location_text(self) -> str:
        return " ".join(x for x in [self.city, self.district] if x)

    def has_city(self, target_city: str) -> bool:
        """Strict-but-practical city match. Unknown city is treated as not matched."""
        target = normalize_city_name(target_city)
        if not target or target in {"不限", "all", "全国"}:
            return True
        loc = normalize_city_name(self.location_text())
        if not loc:
            return False
        return target in loc or loc in target

    def has_keyword(self, keyword: str) -> bool:
        keyword = clean_text(keyword)
        if not keyword:
            return True
        terms = [t.strip().lower() for t in re.split(r"[,，/|\s]+", keyword) if t.strip()]
        if not terms:
            return True
        haystack = " ".join([
            self.title,
            self.company,
            self.description,
            " ".join(self.skills),
        ]).lower()
        return any(t in haystack for t in terms)

    def raw_text(self) -> str:
        parts: list[str] = []
        if self.title:
            parts.append(f"职位名称：{self.title}")
        if self.company:
            parts.append(f"公司：{self.company}")
        if self.salary:
            parts.append(f"薪资：{self.salary}")
        if self.location_text():
            parts.append(f"地点：{self.location_text()}")
        reqs = [x for x in [self.experience, self.degree] if x]
        if reqs:
            parts.append(f"要求：{' / '.join(reqs)}")
        if self.skills:
            parts.append(f"技能标签：{'、'.join(self.skills)}")
        if self.description:
            parts.append("")
            parts.append(self.description)
        return "\n".join(parts).strip()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # raw can be huge/noisy; keep a lightweight copy for exports.
        data.pop("raw", None)
        return data
