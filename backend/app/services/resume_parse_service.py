"""Resume structured parsing service.

Dispatches to either mock (rule-based) or LLM-based extraction
depending on the configured LLM_PROVIDER.
"""

import json
import re

from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.schemas.resume_parse import (
    ParsedResume,
    BasicInfo,
    EducationItem,
    WorkExperienceItem,
    ProjectItem,
    CertificateItem,
    AwardItem,
    RawQualityCheck,
)
from app.services.llm_client import get_llm_client, MockLLMClient
from app.prompts import RESUME_SYSTEM_PROMPT, RESUME_USER_TEMPLATE
from app.core.exceptions import AppException
from app.utils.prompt_render import render_prompt
from app.utils.model_dump import model_to_dict

TOO_SHORT_THRESHOLD = 100  # characters


# ── Public API ─────────────────────────────────────────

def parse_resume(resume_id: int, db: Session) -> ParsedResume:
    """Parse a resume's raw_text into structured JSON and persist it."""
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise AppException(f"Resume {resume_id} not found", code="NOT_FOUND", status_code=404)

    if not resume.raw_text or not resume.raw_text.strip():
        raise AppException(
            "Resume raw_text is empty, cannot parse",
            code="EMPTY_RAW_TEXT",
        )

    client = get_llm_client()
    if isinstance(client, MockLLMClient):
        parsed = _mock_parse(resume.raw_text)
    else:
        user_prompt = render_prompt(RESUME_USER_TEMPLATE, raw_text=resume.raw_text)
        raw_json = client.chat_json(RESUME_SYSTEM_PROMPT, user_prompt)
        parsed = ParsedResume(**raw_json)

    # Quality check
    parsed.raw_quality_check = _quality_check(resume.raw_text, parsed)

    # Persist
    resume.parsed_json = json.dumps(model_to_dict(parsed), ensure_ascii=False)
    db.commit()
    db.refresh(resume)

    return parsed


# ── Mock (rule-based) parser ───────────────────────────

def _mock_parse(raw_text: str) -> ParsedResume:
    """Best-effort extraction using regex and keyword heuristics."""
    text = raw_text.strip()

    basic_info = _extract_basic_info(text)
    education = _extract_education(text)
    work_experience = _extract_work_experience(text)
    projects = _extract_projects(text)
    skills = _extract_skills(text)
    self_evaluation = _extract_section(text, ["自我评价", "个人总结", "自我介绍", "self-evaluation", "summary"])

    return ParsedResume(
        basic_info=basic_info,
        education=education,
        work_experience=work_experience,
        projects=projects,
        skills=skills,
        certificates=[],
        awards=[],
        self_evaluation=self_evaluation,
    )


def _extract_basic_info(text: str) -> BasicInfo:
    info = BasicInfo()

    # Name: first non-empty line that looks like a name (2-4 Chinese chars or capitalized English)
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[一-鿿]{2,4}$", line) or re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+$", line):
            info.name = line
            break

    phone_match = re.search(r"1[3-9]\d{9}", text)
    if phone_match:
        info.phone = phone_match.group()

    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if email_match:
        info.email = email_match.group()

    location_match = re.search(r"(?:籍贯|现居|所在地|地址)[：:]\s*(.+)", text)
    if location_match:
        info.location = location_match.group(1).strip()

    exp_match = re.search(r"(\d+)\s*[年+].*?(?:经验|工作经验|开发经验)", text)
    if exp_match:
        info.years_of_experience = exp_match.group(1)

    return info


def _extract_education(text: str) -> list[EducationItem]:
    items: list[EducationItem] = []
    edu_block = _extract_section(text, ["教育经历", "教育背景", "学历", "education"])

    if not edu_block:
        # Fallback: look for degree keywords anywhere
        if re.search(r"(?:本科|硕士|博士|大专|学士|研究生)", text):
            school_match = re.search(r"([一-鿿]{2,}(?:大学|学院|学校))", text)
            degree_match = re.search(r"(本科|硕士|博士|大专|学士|研究生)", text)
            major_match = re.search(r"(?:专业)[：:]?\s*([一-鿿\w]+)", text)
            items.append(EducationItem(
                school=school_match.group(1) if school_match else "",
                degree=degree_match.group(1) if degree_match else "",
                major=major_match.group(1) if major_match else "",
            ))
        return items

    # Try to split by lines and extract
    for line in edu_block.split("\n"):
        line = line.strip()
        if not line or len(line) < 4:
            continue
        school_match = re.search(r"([一-鿿]{2,}(?:大学|学院|学校))", line)
        degree_match = re.search(r"(本科|硕士|博士|大专|学士|研究生)", line)
        major_match = re.search(r"(?:专业)[：:]?\s*([一-鿿\w]+)", line)
        date_match = re.search(r"(\d{4}[\.\-/]\d{1,2})\s*[-–~至]\s*(\d{4}[\.\-/]\d{1,2}|至今|present)", line, re.IGNORECASE)

        if school_match or degree_match:
            items.append(EducationItem(
                school=school_match.group(1) if school_match else "",
                degree=degree_match.group(1) if degree_match else "",
                major=major_match.group(1) if major_match else "",
                start_date=date_match.group(1) if date_match else "",
                end_date=date_match.group(2) if date_match else "",
            ))

    return items


def _extract_work_experience(text: str) -> list[WorkExperienceItem]:
    items: list[WorkExperienceItem] = []
    work_block = _extract_section(text, ["工作经历", "工作经验", "work experience", "employment"])

    if not work_block:
        return items

    # Split by company-like patterns
    chunks = re.split(r"(?=[一-鿿]{2,}(?:公司|集团|科技|技术|网络|信息))", work_block)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        company_match = re.search(r"([一-鿿]{2,}(?:公司|集团|科技|技术|网络|信息)[一-鿿]*)", chunk)
        title_match = re.search(r"(?:职位|岗位|担任)[：:]?\s*([一-鿿\w]+)", chunk)
        date_match = re.search(r"(\d{4}[\.\-/]\d{1,2})\s*[-–~至]\s*(\d{4}[\.\-/]\d{1,2}|至今|present)", chunk, re.IGNORECASE)

        if company_match:
            items.append(WorkExperienceItem(
                company=company_match.group(1) if company_match else "",
                title=title_match.group(1) if title_match else "",
                start_date=date_match.group(1) if date_match else "",
                end_date=date_match.group(2) if date_match else "",
                description=chunk,
            ))

    return items


def _extract_projects(text: str) -> list[ProjectItem]:
    items: list[ProjectItem] = []
    proj_block = _extract_section(text, ["项目经历", "项目经验", "项目介绍", "projects"])

    if not proj_block:
        return items

    # Split by project-like headers (numbered or named)
    chunks = re.split(r"(?=(?:项目[一二三四五六七八九十\d]|[\d]+[\.、]|Project))", proj_block)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or len(chunk) < 10:
            continue
        name_match = re.search(r"(?:项目名称|项目)[：:]?\s*(.+)", chunk)
        tech_match = re.findall(r"(?:技术栈|技术|使用)[：:]?\s*(.+)", chunk)

        tech_stack: list[str] = []
        if tech_match:
            for t in tech_match:
                tech_stack.extend(re.split(r"[,，、/|]+", t.strip()))

        items.append(ProjectItem(
            name=name_match.group(1).strip() if name_match else "",
            tech_stack=[t.strip() for t in tech_stack if t.strip()],
            description=chunk,
        ))

    return items


def _extract_skills(text: str) -> list[str]:
    skills_block = _extract_section(text, ["技能", "专业技能", "技术栈", "skills", "技术能力"])

    if not skills_block:
        # Fallback: look for common tech keywords anywhere
        tech_keywords = re.findall(
            r"(?:Python|Java|Go|JavaScript|TypeScript|React|Vue|Angular|Node\.?js|"
            r"FastAPI|Django|Flask|Spring|MySQL|PostgreSQL|Redis|MongoDB|"
            r"Docker|Kubernetes|Linux|Git|Nginx|Kafka|RabbitMQ|Elasticsearch|"
            r"HTML|CSS|SQL|C\+\+|Rust|AWS|Azure|GCP)",
            text, re.IGNORECASE,
        )
        return list(set(tech_keywords))

    # Extract from bullet points or comma-separated lists
    skills: list[str] = []
    for line in skills_block.split("\n"):
        line = line.strip().lstrip("•·-–* ")
        if not line:
            continue
        parts = re.split(r"[,，、/|]+", line)
        skills.extend(p.strip() for p in parts if p.strip())

    return list(set(skills))


def _extract_section(text: str, headers: list[str]) -> str:
    """Extract text between a section header and the next section header."""
    for header in headers:
        pattern = rf"(?:^|\n)\s*{re.escape(header)}\s*[:：]?\s*\n?(.*?)(?=\n\s*(?:[一-鿿]{{2,}}[:：]|$))"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


# ── Quality check ──────────────────────────────────────

def _quality_check(raw_text: str, parsed: ParsedResume) -> RawQualityCheck:
    issues: list[str] = []
    is_too_short = len(raw_text.strip()) < TOO_SHORT_THRESHOLD
    missing_projects = len(parsed.projects) == 0
    missing_skills = len(parsed.skills) == 0
    missing_work = len(parsed.work_experience) == 0

    if is_too_short:
        issues.append(f"简历文本过短（{len(raw_text.strip())} 字符），信息可能不完整")
    if missing_projects:
        issues.append("未检测到项目经历，建议补充")
    if missing_skills:
        issues.append("未检测到技能栈，建议补充专业技能")
    if missing_work:
        issues.append("未检测到工作/实习经历")

    return RawQualityCheck(
        is_too_short=is_too_short,
        missing_projects=missing_projects,
        missing_skills=missing_skills,
        missing_work_experience=missing_work,
        issues=issues,
    )
