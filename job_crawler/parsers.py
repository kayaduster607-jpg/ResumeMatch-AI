from __future__ import annotations

import json
import re
from collections import deque
from typing import Any, Iterable
from urllib.parse import urljoin

from .config import PLATFORMS
from .models import JobItem, clean_text


TITLE_KEYS = ("jobName", "positionName", "title", "job_title", "positionTitle", "name")
ID_KEYS = ("encryptJobId", "securityId", "jobId", "job_id", "number", "positionId", "id", "jobNumber")
COMPANY_KEYS = ("brandName", "companyName", "compName", "company", "company_name", "brand", "hiringOrganization")
SALARY_KEYS = ("salaryDesc", "salary", "salary60", "salaryText", "salaryRange", "compensation")
CITY_KEYS = ("cityName", "city", "dq", "jobArea", "cityDistrict", "workCity", "area", "location")
DISTRICT_KEYS = ("areaDistrict", "district", "dqDesc", "businessDistrict", "address")
EXP_KEYS = ("experienceName", "workExperience", "requireWorkYears", "workYear", "experience", "workYearString")
DEGREE_KEYS = ("degreeName", "education", "requireEduLevel", "degree", "eduLevel")
SKILL_KEYS = ("skills", "tags", "labels", "tagList", "skillLabel", "welfareList")
DESC_KEYS = ("jobDesc", "description", "postDescription", "content", "jobDetail", "jobDescription", "positionDesc")
URL_KEYS = ("jobUrl", "url", "pcUrl", "detailUrl", "href", "link")


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _first_value(obj: dict[str, Any], keys: Iterable[str], *, recursive: bool = True) -> Any:
    for key in keys:
        if "." in key:
            val = _get_path(obj, key)
        else:
            val = obj.get(key)
        if _is_nonempty(val):
            return val
    if not recursive:
        return None
    # One-level recursive search handles nested company/city objects without
    # accidentally pulling huge unrelated values.
    for value in obj.values():
        if isinstance(value, dict):
            nested = _first_value(value, keys, recursive=False)
            if _is_nonempty(nested):
                return nested
    return None


def _is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _extract_text_from_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "display", "value", "text", "label", "title"):
            if _is_nonempty(value.get(key)):
                return clean_text(value.get(key))
        return clean_text(" ".join(_extract_text_from_value(v) for v in value.values()))
    if isinstance(value, list):
        return "、".join(x for x in (_extract_text_from_value(v) for v in value) if x)
    return clean_text(value)


def _extract_skills(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,，、/|\s]+", value)
        return [clean_text(p) for p in parts if clean_text(p)]
    if isinstance(value, dict):
        text = _extract_text_from_value(value)
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = _extract_text_from_value(item)
            else:
                text = clean_text(item)
            if text and text not in out:
                out.append(text)
        return out
    text = clean_text(value)
    return [text] if text else []


def _looks_like_job_dict(item: dict[str, Any]) -> bool:
    # Require a title-like field and at least one supporting job signal.
    has_title = any(_is_nonempty(item.get(k)) for k in TITLE_KEYS if k != "name")
    if not has_title and _is_nonempty(item.get("name")):
        has_title = any(_is_nonempty(item.get(k)) for k in ID_KEYS + COMPANY_KEYS + SALARY_KEYS)
    has_signal = any(_is_nonempty(_first_value(item, keys, recursive=True)) for keys in [ID_KEYS, COMPANY_KEYS, SALARY_KEYS, CITY_KEYS])
    return bool(has_title and has_signal)


def _find_job_dicts(data: Any, max_depth: int = 7, max_items: int = 300) -> list[dict[str, Any]]:
    """Find list entries that look like job cards inside arbitrary JSON."""
    found: list[dict[str, Any]] = []
    q: deque[tuple[Any, int]] = deque([(data, 0)])
    seen_objects: set[int] = set()

    while q and len(found) < max_items:
        obj, depth = q.popleft()
        oid = id(obj)
        if oid in seen_objects:
            continue
        seen_objects.add(oid)
        if depth > max_depth:
            continue

        if isinstance(obj, list):
            if obj and all(isinstance(x, dict) for x in obj):
                hits = [x for x in obj if _looks_like_job_dict(x)]
                if hits:
                    found.extend(hits)
                    continue
            for value in obj[:max_items]:
                q.append((value, depth + 1))
        elif isinstance(obj, dict):
            if _looks_like_job_dict(obj):
                found.append(obj)
                continue
            # Prioritize common container keys before generic recursion.
            preferred_keys = (
                "jobList", "jobCardList", "list", "items", "data", "results", "result", "resultbody",
                "positionList", "jobInfoList", "pageData", "zpData", "searchResult",
            )
            for key in preferred_keys:
                if key in obj:
                    q.append((obj[key], depth + 1))
            for key, value in obj.items():
                if key not in preferred_keys and isinstance(value, (dict, list)):
                    q.append((value, depth + 1))
    return found[:max_items]


def _make_abs_url(platform: str, url: str) -> str:
    url = clean_text(url)
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return urljoin(PLATFORMS[platform].home_url, url)


def job_from_dict(platform: str, item: dict[str, Any], source_url: str = "") -> JobItem | None:
    cfg = PLATFORMS[platform]
    title = clean_text(_first_value(item, TITLE_KEYS), 120)
    # Some APIs put title under nested position.name.
    if not title:
        title = clean_text(_get_path(item, "position.name") or _get_path(item, "job.name"), 120)
    if not title or len(title) < 2:
        return None

    job_id = clean_text(_first_value(item, ID_KEYS), 160)
    security_id = clean_text(item.get("securityId") or item.get("lid") or item.get("encryptJobId"), 160)
    company = clean_text(
        _get_path(item, "company.name")
        or _get_path(item, "brand.name")
        or _get_path(item, "hiringOrganization.name")
        or _first_value(item, COMPANY_KEYS),
        160,
    )
    salary = clean_text(_first_value(item, SALARY_KEYS), 120)
    city = clean_text(
        _get_path(item, "city.display")
        or _get_path(item, "jobLocation.address.addressLocality")
        or _first_value(item, CITY_KEYS),
        120,
    )
    district = clean_text(_first_value(item, DISTRICT_KEYS), 160)
    experience = clean_text(_first_value(item, EXP_KEYS), 80)
    degree = clean_text(_first_value(item, DEGREE_KEYS), 80)
    skills = _extract_skills(_first_value(item, SKILL_KEYS))[:20]
    description = clean_text(_first_value(item, DESC_KEYS), 12000)
    url = _make_abs_url(platform, clean_text(_first_value(item, URL_KEYS), 400))

    # BOSS detail URL needs both encryptJobId and securityId; keep API fields for later.
    if not url and platform == "boss" and job_id:
        url = f"https://www.zhipin.com/job_detail/{job_id}.html"
    if not url and platform == "liepin" and job_id:
        url = f"https://www.liepin.com/job/{job_id}.shtml"
    if not url and platform == "qiancheng" and job_id:
        url = f"https://we.51job.com/pc/job/{job_id}.html"

    return JobItem(
        platform=platform,
        platform_name=cfg.name,
        job_id=job_id,
        security_id=security_id,
        title=title,
        company=company,
        salary=salary,
        city=city,
        district=district,
        experience=experience,
        degree=degree,
        skills=skills,
        description=description,
        url=url,
        source_url=source_url,
        raw=item,
    )


def extract_jobs_from_json(platform: str, data: Any, source_url: str = "") -> list[JobItem]:
    """Convert platform JSON responses into normalized JobItem rows."""
    if data is None:
        return []

    job_dicts: list[dict[str, Any]] = []

    # Fast paths for known response shapes.
    if isinstance(data, dict):
        known_paths = [
            "zpData.jobList",
            "data.jobList",
            "data.jobCardList",
            "data.list",
            "data.items",
            "data.results",
            "data.data.list",
            "resultbody.job.items",
            "resultbody.items",
            "searchResult.list",
        ]
        for path in known_paths:
            val = _get_path(data, path)
            if isinstance(val, list):
                job_dicts.extend(x for x in val if isinstance(x, dict))

    if not job_dicts:
        job_dicts = _find_job_dicts(data)

    jobs: list[JobItem] = []
    seen: set[str] = set()
    for item in job_dicts:
        job = job_from_dict(platform, item, source_url=source_url)
        if not job:
            continue
        key = job.key()
        if key in seen:
            continue
        seen.add(key)
        jobs.append(job)
    return jobs


def parse_json_from_body_text(text: str) -> Any | None:
    text = clean_text(text)
    if not text:
        return None
    # Chromium often renders JSON inside a <pre> as plain text.
    candidates = [text]
    match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
    if match:
        candidates.append(match.group(1))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def extract_detail_from_json(platform: str, data: Any) -> dict[str, str] | None:
    """Best-effort extraction of a single detail payload into text fields."""
    if not isinstance(data, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for path in [
        "zpData.jobInfo",
        "zpData.brandComInfo",
        "data.position",
        "data.jobInfo",
        "data.jobDetail",
        "jobDetail",
        "jobInfo",
        "position",
        "data",
    ]:
        val = _get_path(data, path)
        if isinstance(val, dict):
            candidates.append(val)

    merged: dict[str, Any] = {}
    for c in reversed(candidates):
        merged.update(c)
    if not merged:
        return None

    title = clean_text(_first_value(merged, TITLE_KEYS) or _get_path(merged, "position.name"), 160)
    company = clean_text(_get_path(merged, "company.name") or _first_value(merged, COMPANY_KEYS), 160)
    salary = clean_text(_first_value(merged, SALARY_KEYS), 120)
    city = clean_text(_get_path(merged, "city.display") or _first_value(merged, CITY_KEYS), 120)
    description = clean_text(_first_value(merged, DESC_KEYS), 20000)
    if not any([title, company, salary, city, description]):
        return None
    parts = []
    if title:
        parts.append(f"职位名称：{title}")
    if company:
        parts.append(f"公司：{company}")
    if salary:
        parts.append(f"薪资：{salary}")
    if city:
        parts.append(f"地点：{city}")
    if description:
        parts.extend(["", description])
    return {
        "title": title,
        "company": company,
        "salary": salary,
        "city": city,
        "description": description,
        "raw_text": "\n".join(parts).strip(),
    }


DOM_EXTRACTOR_JS = r"""
(platform) => {
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const abs = (href) => {
    if (!href) return '';
    try { return new URL(href, location.href).href; } catch { return href; }
  };
  const firstText = (root, selectors) => {
    for (const sel of selectors) {
      const el = root.querySelector(sel);
      const text = clean(el?.innerText || el?.textContent || el?.getAttribute('title') || '');
      if (text) return text;
    }
    return '';
  };
  const linkOf = (root) => {
    const a = root.querySelector("a[href*='job'], a[href*='position'], a[href*='detail']") || (root.tagName === 'A' ? root : null);
    return a ? abs(a.href) : '';
  };
  const idFromUrl = (url) => {
    if (!url) return '';
    const patterns = [
      /job_detail\/([^/?#]+)\.html/i,
      /jobdetail\/([^/?#]+)/i,
      /jobs\.zhaopin\.com\/([^/?#]+)/i,
      /\/job\/([^/?#]+)\.shtml/i,
      /\/pc\/job\/([^/?#]+)\.html/i,
      /jobid=([^&#]+)/i,
      /position\/([^/?#]+)/i
    ];
    for (const p of patterns) {
      const m = url.match(p);
      if (m) return decodeURIComponent(m[1]);
    }
    return '';
  };
  const cardSelectors = [
    '.job-card', '.job-card-box', '.job-list-item', '.joblist-item', '.job-item', '.j_jobitem',
    '[class*=JobCard]', '[class*=job-card]', '[class*=position-card]', '[class*=position-item]',
    '[class*=joblist] [class*=item]', '[class*=positionlist] [class*=item]',
    'a[href*="job_detail"]', 'a[href*="jobdetail"]', 'a[href*="/job/"]', 'a[href*="jobs.zhaopin"]'
  ];
  const nodes = Array.from(document.querySelectorAll(cardSelectors.join(',')));
  const seen = new Set();
  const jobs = [];
  for (const card of nodes) {
    if (jobs.length >= 80) break;
    const title = firstText(card, [
      '[class*=job-name]', '[class*=jobName]', '[class*=job-title]', '[class*=positionName]', '[class*=position-name]',
      '[class*=title]', '[class*=name]', '.jname', 'h3', 'h2', 'a'
    ]);
    if (!title || title.length < 2 || title.length > 120) continue;
    const href = linkOf(card);
    const company = firstText(card, ['[class*=company]', '[class*=comp]', '[class*=brand]', '.cname', '.company-name']);
    const salary = firstText(card, ['[class*=salary]', '[class*=sal]', '[class*=money]']);
    const city = firstText(card, ['[class*=city]', '[class*=area]', '[class*=addr]', '[class*=location]', '[class*=dq]']);
    const metaText = clean(card.innerText || '');
    const key = [platform, title, company, href].join('|');
    if (seen.has(key)) continue;
    seen.add(key);
    jobs.push({
      jobName: title,
      companyName: company,
      salary,
      cityName: city,
      jobId: idFromUrl(href),
      url: href,
      description: metaText.length > 30 && metaText.length < 1500 ? metaText : ''
    });
  }
  return jobs;
}
"""


DETAIL_EXTRACTOR_JS = r"""
() => {
  const clean = (s) => (s || '').replace(/\r/g, '\n').replace(/[\t\f\v]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  const text = (sel) => {
    const el = document.querySelector(sel);
    return clean(el?.innerText || el?.textContent || '');
  };
  const first = (selectors) => {
    for (const sel of selectors) {
      const t = text(sel);
      if (t) return t;
    }
    return '';
  };
  const stripHtml = (s) => clean((s || '').replace(/<br\s*\/?/gi, '\n').replace(/<[^>]+>/g, ''));

  let jsonLd = {};
  for (const node of Array.from(document.querySelectorAll('script[type="application/ld+json"]'))) {
    try {
      const parsed = JSON.parse(node.textContent || '{}');
      if (parsed && (parsed.title || parsed.description || parsed.hiringOrganization)) {
        jsonLd = parsed;
        break;
      }
    } catch {}
  }

  const title = clean(jsonLd.title) || first(['.job-name', '.job-title h1', '.job-title', '.summary-plane__title', '.jname', 'h1']);
  const company = clean(jsonLd.hiringOrganization?.name) || first(['.company-name', '.company-title a', '.cname a', '.comp-name', '[class*=company-name]', '[class*=company]']);
  const salary = first(['.salary', '.job-salary', '.summary-plane__salary', '.cn strong', '.sal', '[class*=salary]', '[class*=sal]']);
  const city = clean(jsonLd.jobLocation?.address?.addressLocality) || first(['.job-area', '.job-dq', '.summary-plane__info', '.job_msg .ltype', '[class*=location]', '[class*=address]', '[class*=city]']);
  const description = stripHtml(jsonLd.description) || first([
    '.job-sec-text', '.describtion__detail-content', '.job-intro-container', '.job-detail', '.job-desc',
    '.bmsg', '.job_msg', '[class*=job-detail]', '[class*=job-content]', '[class*=job-intro]', '[class*=description]'
  ]);
  const body = clean(document.body?.innerText || '');
  const fallbackDesc = description || (body.length > 80 ? body.slice(0, 5000) : '');
  const parts = [];
  if (title) parts.push(`职位名称：${title}`);
  if (company) parts.push(`公司：${company}`);
  if (salary) parts.push(`薪资：${salary}`);
  if (city) parts.push(`地点：${city}`);
  if (fallbackDesc) parts.push('', fallbackDesc);
  return { title, company, salary, city, description: fallbackDesc, raw_text: parts.join('\n').trim(), url: location.href };
}
"""
