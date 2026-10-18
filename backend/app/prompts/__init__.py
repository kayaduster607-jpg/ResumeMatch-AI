"""Prompt templates for LLM calls."""

from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


def _read_prompt(filename: str) -> str:
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


_marker = "## User Prompt Template"


# ── Resume extraction ──────────────────────────────────

RESUME_SYSTEM_PROMPT = (
    "You are a resume parsing engine. "
    "Given raw resume text, extract structured information and return ONLY a valid JSON object. "
    "Do not include any explanation, markdown, or commentary."
)

_RESUME_TEMPLATE_RAW = _read_prompt("resume_extract.md")
RESUME_USER_TEMPLATE = _RESUME_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _RESUME_TEMPLATE_RAW else ""


# ── JD extraction ──────────────────────────────────────

JD_SYSTEM_PROMPT = (
    "You are a job description parsing engine. "
    "Given raw JD text, extract structured information and return ONLY a valid JSON object. "
    "Do not include any explanation, markdown, or commentary."
)

_JD_TEMPLATE_RAW = _read_prompt("jd_extract.md")
JD_USER_TEMPLATE = _JD_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _JD_TEMPLATE_RAW else ""


# ── Match scoring ──────────────────────────────────────

MATCH_SYSTEM_PROMPT = (
    "You are a resume-job matching analyst. "
    "Evaluate the match quality across four dimensions and return ONLY a valid JSON object. "
    "Do not include any explanation, markdown, or commentary."
)

_MATCH_TEMPLATE_RAW = _read_prompt("match_score.md")
MATCH_USER_TEMPLATE = _MATCH_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _MATCH_TEMPLATE_RAW else ""


# ── Resume diagnosis ───────────────────────────────────

DIAGNOSIS_SYSTEM_PROMPT = (
    "You are a resume diagnosis expert. "
    "Identify specific issues in the resume and provide actionable suggestions with rewrite examples. "
    "Return ONLY a valid JSON array. "
    "Do not include any explanation, markdown, or commentary."
)

_DIAGNOSIS_TEMPLATE_RAW = _read_prompt("resume_diagnosis.md")
DIAGNOSIS_USER_TEMPLATE = _DIAGNOSIS_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _DIAGNOSIS_TEMPLATE_RAW else ""


# ── Resume rewrite ─────────────────────────────────────

REWRITE_SYSTEM_PROMPT = (
    "You are a resume writing coach. "
    "Rewrite project descriptions to better match the target role. "
    "DO NOT fabricate experience or data. Return ONLY a valid JSON object. "
    "Do not include any explanation, markdown, or commentary."
)

_REWRITE_TEMPLATE_RAW = _read_prompt("resume_rewrite.md")
REWRITE_USER_TEMPLATE = _REWRITE_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _REWRITE_TEMPLATE_RAW else ""


# ── Interview question generation ──────────────────────

INTERVIEW_SYSTEM_PROMPT = (
    "You are an experienced technical interviewer. "
    "Generate targeted interview questions. Return ONLY a valid JSON array. "
    "Do not include any explanation, markdown, or commentary."
)

_INTERVIEW_TEMPLATE_RAW = _read_prompt("interview_question_generate.md")
INTERVIEW_USER_TEMPLATE = _INTERVIEW_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _INTERVIEW_TEMPLATE_RAW else ""


# ── Mock interview scoring ─────────────────────────────

MOCK_INTERVIEW_SYSTEM_PROMPT = (
    "You are an experienced technical interviewer. "
    "Evaluate the candidate's interview answer and provide detailed feedback. "
    "Return ONLY a valid JSON object. "
    "Do not include any explanation, markdown, or commentary."
)

_MOCK_INTERVIEW_TEMPLATE_RAW = _read_prompt("mock_interview_score.md")
MOCK_INTERVIEW_USER_TEMPLATE = _MOCK_INTERVIEW_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _MOCK_INTERVIEW_TEMPLATE_RAW else ""


# ── Report generation ──────────────────────────────────

REPORT_SYSTEM_PROMPT = (
    "You are a career advisor. "
    "Generate a comprehensive resume analysis report. Return ONLY a valid JSON object. "
    "Do not include any explanation, markdown, or commentary."
)

_REPORT_TEMPLATE_RAW = _read_prompt("report_generate.md")
REPORT_USER_TEMPLATE = _REPORT_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _REPORT_TEMPLATE_RAW else ""


# ── Full resume rewrite ───────────────────────────────

FULL_REWRITE_SYSTEM_PROMPT = (
    "你是一位有10年经验的中文技术岗简历优化顾问。"
    "你的任务是把候选人的真实经历改写成可以直接投递的中文简历，不是写建议报告。"
    "绝不编造不存在的经历、技能、公司、学校、奖项或数字；缺失但重要的信息用[请补充：...]占位。"
    "输出必须严格是JSON，不要Markdown，不要解释。"
)

_FULL_REWRITE_TEMPLATE_RAW = _read_prompt("full_resume_rewrite.md")
FULL_REWRITE_USER_TEMPLATE = _FULL_REWRITE_TEMPLATE_RAW.split(_marker, 1)[1].strip() if _marker in _FULL_REWRITE_TEMPLATE_RAW else ""
