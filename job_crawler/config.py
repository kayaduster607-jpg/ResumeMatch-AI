from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode, quote


@dataclass(frozen=True)
class PlatformConfig:
    key: str
    name: str
    home_url: str
    page_size: int
    domains: tuple[str, ...]
    detail_prefix: str
    detail_suffix: str = ""


PLATFORMS: dict[str, PlatformConfig] = {
    "boss": PlatformConfig(
        key="boss",
        name="BOSS直聘",
        home_url="https://www.zhipin.com/web/geek/job",
        page_size=30,
        domains=("zhipin.com",),
        detail_prefix="https://www.zhipin.com/job_detail/",
        detail_suffix=".html",
    ),
    "zhaopin": PlatformConfig(
        key="zhaopin",
        name="智联招聘",
        home_url="https://sou.zhaopin.com/",
        page_size=30,
        domains=("zhaopin.com",),
        detail_prefix="https://www.zhaopin.com/jobdetail/",
    ),
    "liepin": PlatformConfig(
        key="liepin",
        name="猎聘",
        home_url="https://www.liepin.com/zhaopin/",
        page_size=40,
        domains=("liepin.com",),
        detail_prefix="https://www.liepin.com/job/",
        detail_suffix=".shtml",
    ),
    "qiancheng": PlatformConfig(
        key="qiancheng",
        name="前程无忧",
        home_url="https://www.51job.com/",
        page_size=20,
        domains=("51job.com",),
        detail_prefix="https://we.51job.com/pc/job/",
        detail_suffix=".html",
    ),
}

DEFAULT_PLATFORMS = tuple(PLATFORMS.keys())

# 城市 code 使用原插件中已经验证过的一组常用城市，按平台分开，避免跨平台串码。
CITY_CODES: dict[str, dict[str, str]] = {
    "北京": {"boss": "101010100", "zhaopin": "530", "liepin": "010", "qiancheng": "010000"},
    "上海": {"boss": "101020100", "zhaopin": "538", "liepin": "020", "qiancheng": "020000"},
    "广州": {"boss": "101280100", "zhaopin": "763", "liepin": "050020", "qiancheng": "030200"},
    "深圳": {"boss": "101280600", "zhaopin": "765", "liepin": "050090", "qiancheng": "040000"},
    "杭州": {"boss": "101210100", "zhaopin": "653", "liepin": "070020", "qiancheng": "080200"},
    "成都": {"boss": "101270100", "zhaopin": "801", "liepin": "280020", "qiancheng": "090200"},
    "天津": {"boss": "101030100", "zhaopin": "531", "liepin": "030", "qiancheng": "050000"},
    "西安": {"boss": "101110100", "zhaopin": "854", "liepin": "270020", "qiancheng": "200200"},
    "武汉": {"boss": "101050100", "zhaopin": "736", "liepin": "170020", "qiancheng": "180200"},
    "南京": {"boss": "101180100", "zhaopin": "635", "liepin": "060020", "qiancheng": "070200"},
    "苏州": {"boss": "101190100", "zhaopin": "639", "liepin": "060080", "qiancheng": "070300"},
    "长沙": {"boss": "101200100", "zhaopin": "749", "liepin": "180020", "qiancheng": "140300"},
    "厦门": {"boss": "101230100", "zhaopin": "682", "liepin": "090040", "qiancheng": "110300"},
    "重庆": {"boss": "101160100", "zhaopin": "811", "liepin": "040030", "qiancheng": "060000"},
    "东莞": {"boss": "101250100", "zhaopin": "769", "liepin": "050060", "qiancheng": "030800"},
    "济南": {"boss": "101120100", "zhaopin": "702", "liepin": "120020", "qiancheng": "120300"},
    "合肥": {"boss": "101220100", "zhaopin": "664", "liepin": "150020", "qiancheng": "150200"},
    "珠海": {"boss": "101330100", "zhaopin": "773", "liepin": "050050", "qiancheng": "030500"},
}


def normalize_platforms(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None or value == "all":
        return list(DEFAULT_PLATFORMS)
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace("，", ",").split(",") if p.strip()]
    else:
        parts = list(value)
    aliases = {
        "boss直聘": "boss",
        "boss": "boss",
        "zhipin": "boss",
        "智联": "zhaopin",
        "智联招聘": "zhaopin",
        "zhaopin": "zhaopin",
        "猎聘": "liepin",
        "liepin": "liepin",
        "前程无忧": "qiancheng",
        "51job": "qiancheng",
        "qiancheng": "qiancheng",
    }
    result: list[str] = []
    for part in parts:
        key = aliases.get(part.lower(), aliases.get(part, part.lower()))
        if key not in PLATFORMS:
            raise ValueError(f"未知平台: {part}; 支持: {', '.join(PLATFORMS)}")
        if key not in result:
            result.append(key)
    return result or list(DEFAULT_PLATFORMS)


def get_city_code(platform: str, city: str) -> str:
    city = (city or "").strip()
    if not city or city in {"不限", "全国", "all"}:
        return ""
    # Already a likely code.
    if city.isdigit() or (platform == "liepin" and city.replace("0", "").isdigit()):
        return city
    if city.endswith("市"):
        city = city[:-1]
    return CITY_CODES.get(city, {}).get(platform, city)


def build_search_url(
    platform: str,
    keyword: str,
    city: str,
    page: int = 1,
    experience: str = "",
    degree: str = "",
    job_type: str = "",
) -> str:
    page = max(page, 1)
    keyword = keyword.strip()
    city_code = get_city_code(platform, city)

    if platform == "boss":
        params = {
            "query": keyword,
            "city": city_code or "101280100",
            "page": str(page),
            "pageSize": "30",
        }
        if job_type:
            params["jobNature"] = job_type
        if experience:
            params["experience"] = experience
        if degree:
            params["degree"] = degree
        return "https://www.zhipin.com/wapi/zpgeek/search/joblist.json?" + urlencode(params)

    if platform == "zhaopin":
        params = {
            "pageSize": "30",
            "cityId": city_code or "530",
            "kw": keyword,
            "kt": "3",
            "workExperience": experience or "-1",
            "education": degree or "-1",
            "employmentType": job_type or "-1",
            "pageIndex": str(page - 1),
        }
        return "https://sou.zhaopin.com/?" + urlencode(params)

    if platform == "liepin":
        params = {
            "key": keyword,
            "dq": city_code,
            "currentPage": str(page - 1),
            "pageSize": "40",
        }
        return "https://www.liepin.com/zhaopin/?" + urlencode(params)

    if platform == "qiancheng":
        params = {
            "jobArea": city_code or "010000",
            "keyword": keyword,
            "searchType": "1",
            "page": str(page),
            "pageSize": "20",
        }
        if experience:
            params["workYearCode"] = experience
        if degree:
            params["educationCode"] = degree
        return "https://we.51job.com/pc/search?" + urlencode(params)

    raise ValueError(f"Unsupported platform: {platform}")


def build_detail_url(platform: str, job_id: str, url: str = "") -> str:
    if url and url.startswith("http"):
        return url
    cfg = PLATFORMS[platform]
    if not job_id:
        return cfg.home_url
    return f"{cfg.detail_prefix}{quote(str(job_id))}{cfg.detail_suffix}"
