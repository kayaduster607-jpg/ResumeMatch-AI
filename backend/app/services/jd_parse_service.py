"""JD structured parsing service.

Dispatches to mock (rule-based) or LLM-based extraction.
Includes skill normalization for deduplication.
"""

import json
from typing import Optional
import re

from sqlalchemy.orm import Session

from app.models.job_description import JobDescription
from app.schemas.jd import ParsedJD
from app.services.llm_client import get_llm_client, MockLLMClient
from app.prompts import JD_SYSTEM_PROMPT, JD_USER_TEMPLATE
from app.core.exceptions import AppException
from app.utils.prompt_render import render_prompt
from app.utils.model_dump import model_to_dict


# ── Public API ─────────────────────────────────────────

def parse_jd(jd_id: int, db: Session) -> ParsedJD:
    """Parse a JD's raw_text into structured JSON and persist it."""
    jd = db.get(JobDescription, jd_id)
    if jd is None:
        raise AppException(f"JobDescription {jd_id} not found", code="NOT_FOUND", status_code=404)

    if not jd.raw_text or not jd.raw_text.strip():
        raise AppException("JD raw_text is empty, cannot parse", code="EMPTY_RAW_TEXT")

    client = get_llm_client()
    if isinstance(client, MockLLMClient):
        parsed = _mock_parse_jd(jd.raw_text, jd.title, jd.company)
    else:
        user_prompt = render_prompt(JD_USER_TEMPLATE, raw_text=jd.raw_text)
        raw_json = client.chat_json(JD_SYSTEM_PROMPT, user_prompt)
        parsed = ParsedJD(**raw_json)

    # Normalize and deduplicate skills
    parsed.required_skills = _normalize_skills(parsed.required_skills)
    parsed.preferred_skills = _normalize_skills(parsed.preferred_skills)
    parsed.tools = _normalize_skills(parsed.tools)
    parsed.programming_languages = _normalize_skills(parsed.programming_languages)
    parsed.frameworks = _normalize_skills(parsed.frameworks)
    parsed.databases = _normalize_skills(parsed.databases)

    # Fill title/company from DB if parser didn't extract
    if not parsed.job_title and jd.title:
        parsed.job_title = jd.title
    if not parsed.company and jd.company:
        parsed.company = jd.company

    # Persist
    jd.parsed_json = json.dumps(model_to_dict(parsed), ensure_ascii=False)
    db.commit()
    db.refresh(jd)

    return parsed


# ── Skill normalization ────────────────────────────────

_SKILL_ALIASES: dict[str, str] = {
    "python": "Python", "python3": "Python", "py": "Python",
    "javascript": "JavaScript", "js": "JavaScript", "es6": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "java": "Java",
    "golang": "Go", "go": "Go",
    "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#",
    "rust": "Rust",
    "php": "PHP",
    "ruby": "Ruby",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "react": "React", "reactjs": "React", "react.js": "React",
    "vue": "Vue", "vuejs": "Vue", "vue.js": "Vue",
    "angular": "Angular", "angularjs": "Angular",
    "nextjs": "Next.js", "next.js": "Next.js",
    "nuxt": "Nuxt.js", "nuxtjs": "Nuxt.js",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "express": "Express", "expressjs": "Express",
    "fastapi": "FastAPI", "fast-api": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring", "springboot": "Spring Boot", "spring boot": "Spring Boot",
    "gin": "Gin",
    "laravel": "Laravel",
    "rails": "Rails", "ruby on rails": "Rails",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "pg": "PostgreSQL",
    "mongodb": "MongoDB", "mongo": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch", "es": "Elasticsearch", "elastic": "Elasticsearch",
    "sqlite": "SQLite",
    "oracle": "Oracle",
    "sql server": "SQL Server", "sqlserver": "SQL Server",
    "docker": "Docker",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "nginx": "Nginx",
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP",
    "azure": "Azure",
    "linux": "Linux",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "ci/cd": "CI/CD", "cicd": "CI/CD",
    "kafka": "Kafka", "apache kafka": "Kafka",
    "rabbitmq": "RabbitMQ", "rabbit mq": "RabbitMQ",
    "graphql": "GraphQL", "graph ql": "GraphQL",
    "grpc": "gRPC",
    "restful": "RESTful", "rest": "RESTful", "rest api": "RESTful",
    "html": "HTML", "html5": "HTML",
    "css": "CSS", "css3": "CSS",
    "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS",
    "webpack": "Webpack",
    "vite": "Vite",
    "pytorch": "PyTorch", "py torch": "PyTorch",
    "tensorflow": "TensorFlow", "tf": "TensorFlow",
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn",
    "pandas": "pandas",
    "numpy": "NumPy",
    "spark": "Spark", "apache spark": "Spark",
    "flink": "Flink", "apache flink": "Flink",
    "hadoop": "Hadoop",
}


def _normalize_skills(skills: list[str]) -> list[str]:
    """Normalize and deduplicate a list of skill names."""
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        key = skill.strip().lower()
        if not key:
            continue
        normalized = _SKILL_ALIASES.get(key, skill.strip())
        if normalized.lower() not in seen:
            seen.add(normalized.lower())
            result.append(normalized)
    return result


# ── Mock (rule-based) parser ───────────────────────────

def _mock_parse_jd(raw_text: str, title: Optional[str], company: Optional[str]) -> ParsedJD:
    """Best-effort JD extraction using regex and keyword heuristics."""
    text = raw_text.strip()
    lines = text.split("\n")

    responsibilities = _extract_list_section(text, ["岗位职责", "工作职责", "职责描述", "responsibilities", "job responsibilities", "你将"])
    required = _extract_list_section(text, ["任职要求", "岗位要求", "必备条件", "requirements", "qualifications", "must have", "我们需要你"])
    preferred = _extract_list_section(text, ["加分项", "优先", "nice to have", "preferred", "plus"])

    # Also try to extract from lines that look like requirements (for card-level text)
    if not required and not responsibilities:
        for line in lines:
            line = line.strip()
            if any(kw in line for kw in ["负责", "参与", "开发", "设计", "实现", "维护", "熟悉", "了解", "掌握", "具备"]):
                if 10 < len(line) < 200:
                    responsibilities.append(line)

    # Extract structured skills from required + preferred + title + full text
    all_text = " ".join(required) + " " + " ".join(preferred) + " " + text
    # Also extract from title (e.g. "Python后端开发" -> Python)
    title_text = title or ""
    programming_languages = _extract_programming_languages(all_text + " " + title_text)
    frameworks = _extract_frameworks(all_text + " " + title_text)
    tools = _extract_tools(all_text)
    databases = _extract_databases(all_text)
    required_skills = _extract_tech_skills_from_list(required) if required else []
    preferred_skills = _extract_tech_skills_from_list(preferred) if preferred else []

    # If no skills found from sections, extract from full text
    if not required_skills:
        required_skills = _extract_programming_languages(all_text + " " + title_text) + _extract_frameworks(all_text + " " + title_text) + _extract_databases(all_text)
        required_skills = list(set(required_skills))

    edu_req = _extract_requirement(text, ["学历", "education", "学士", "硕士", "本科", "大专"])
    exp_req = _extract_requirement(text, ["经验", "experience", "年限", "年"])
    seniority = _detect_seniority(text)
    soft_skills = _extract_soft_skills(text)
    keywords = _extract_keywords(text)

    # Build summary
    summary_parts = []
    if title:
        summary_parts.append(f"岗位: {title}")
    if company:
        summary_parts.append(f"公司: {company}")
    if required_skills:
        summary_parts.append(f"核心技能: {', '.join(required_skills[:5])}")
    if edu_req:
        summary_parts.append(f"学历要求: {edu_req}")
    if exp_req:
        summary_parts.append(f"经验要求: {exp_req}")

    return ParsedJD(
        job_title=title or "",
        company=company or "",
        responsibilities=responsibilities,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        tools=tools,
        programming_languages=programming_languages,
        frameworks=frameworks,
        databases=databases,
        education_requirement=edu_req,
        experience_requirement=exp_req,
        soft_skills=soft_skills,
        keywords=keywords,
        seniority_level=seniority,
        raw_summary="; ".join(summary_parts),
    )


def _extract_list_section(text: str, headers: list[str]) -> list[str]:
    """Extract bullet-pointed items under a section header."""
    for header in headers:
        # Match header followed by content until next header or end
        pattern = rf"(?:^|\n)\s*{re.escape(header)}\s*[:：]?\s*\n(.*?)(?=\n\s*(?:[一-鿿]{{2,}}[:：]|[-=]{{3,}}|$))"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            block = match.group(1)
            items: list[str] = []
            for line in block.split("\n"):
                line = line.strip()
                # Remove bullet markers
                cleaned = re.sub(r"^[\s]*[•·\-\–\*①②③④⑤⑥⑦⑧⑨⑩\d+[\.、)）]]\s*", "", line)
                if cleaned and len(cleaned) > 2:
                    items.append(cleaned)
            if items:
                return items

    # Fallback: look for numbered/bulleted items anywhere that match patterns
    items = []
    for line in text.split("\n"):
        line = line.strip()
        cleaned = re.sub(r"^[\s]*[•·\-\–\*①②③④⑤⑥⑦⑧⑨⑩\d+[\.、)）]]\s*", "", line)
        if cleaned and 5 < len(cleaned) < 200:
            # Check if it looks like a responsibility or requirement
            if any(kw in cleaned for kw in ["负责", "参与", "熟悉", "了解", "掌握", "具备", "能够", "有", "开发", "设计", "维护"]):
                items.append(cleaned)
    return items[:15]  # Cap at 15 items


def _extract_programming_languages(text: str) -> list[str]:
    langs = re.findall(
        r"(?:Python|Java|Go|Golang|JavaScript|TypeScript|C\+\+|C#|Rust|PHP|Ruby|Swift|Kotlin|Scala|R\b|MATLAB|Shell|Bash)",
        text, re.IGNORECASE,
    )
    return list(set(langs))


def _extract_frameworks(text: str) -> list[str]:
    frameworks = re.findall(
        r"(?:React|Vue|Angular|Next\.?js|Nuxt\.?js|Node\.?js|Express|FastAPI|Django|Flask|"
        r"Spring\s*Boot|Spring|Gin|Laravel|Rails|Ruby\s*on\s*Rails|"
        r"PyTorch|TensorFlow|Keras|scikit-learn|Pandas|NumPy|"
        r"Tailwind\s*CSS|Bootstrap|Material-?UI|Ant\s*Design|"
        r"Webpack|Vite|Babel|ESLint)",
        text, re.IGNORECASE,
    )
    return list(set(frameworks))


def _extract_tools(text: str) -> list[str]:
    tools = re.findall(
        r"(?:Docker|Kubernetes|K8s|Nginx|Git|GitHub|GitLab|Jenkins|"
        r"CI/CD|Terraform|Ansible|Prometheus|Grafana|"
        r"Kafka|RabbitMQ|Redis|Elasticsearch|"
        r"VS\s*Code|IntelliJ|PyCharm|Postman|Jira)",
        text, re.IGNORECASE,
    )
    return list(set(tools))


def _extract_databases(text: str) -> list[str]:
    dbs = re.findall(
        r"(?:MySQL|PostgreSQL|MongoDB|Redis|SQLite|Oracle|SQL\s*Server|"
        r"Elasticsearch|ClickHouse|TiDB|Cassandra|DynamoDB|Neo4j)",
        text, re.IGNORECASE,
    )
    return list(set(dbs))


def _extract_tech_skills_from_list(items: list[str]) -> list[str]:
    """Extract tech skill names from a list of requirement strings."""
    all_text = " ".join(items)
    skills = _extract_programming_languages(all_text) + _extract_frameworks(all_text) + _extract_databases(all_text)
    return list(set(skills))


def _extract_requirement(text: str, keywords: list[str]) -> str:
    """Extract a requirement sentence containing any of the keywords."""
    for line in text.split("\n"):
        line = line.strip()
        if any(kw in line for kw in keywords) and 5 < len(line) < 100:
            # Filter out lines that are clearly not requirements (benefits, perks, etc.)
            if any(skip in line for skip in ["股票期权", "团建", "保险", "补贴", "健身", "年终奖", "体检", "年假", "餐补", "绩效奖金", "租房"]):
                continue
            return line
    return ""


def _detect_seniority(text: str) -> str:
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["lead", "principal", "架构师", "技术负责人", "director"]):
        return "lead"
    if any(kw in text_lower for kw in ["senior", "高级", "资深", "5年以上", "5+ year"]):
        return "senior"
    if any(kw in text_lower for kw in ["junior", "初级", "实习", "intern", "应届", "0-2年"]):
        return "junior"
    return "mid"


def _extract_soft_skills(text: str) -> list[str]:
    patterns = {
        "沟通能力": r"沟通",
        "团队协作": r"团队[协作合作]",
        "学习能力": r"学习能力|快速学习",
        "解决问题": r"解决[问事]题|problem.solving",
        "责任心": r"责任[心感]",
        "抗压能力": r"抗压|压力",
        "自驱力": r"自驱|主动",
    }
    result = []
    for name, pattern in patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            result.append(name)
    return result


def _extract_keywords(text: str) -> list[str]:
    """Extract high-frequency meaningful keywords."""
    # Chinese keywords
    cn_keywords = re.findall(r"[一-鿿]{2,6}", text)
    # Filter out common stop words
    stop_words = {"岗位职责", "任职要求", "加分项", "工作地点", "薪资待遇", "福利待遇", "公司介绍"}
    cn_filtered = [w for w in cn_keywords if w not in stop_words and len(w) >= 2]

    # Count frequency
    from collections import Counter
    counter = Counter(cn_filtered)
    return [word for word, _ in counter.most_common(20)]
