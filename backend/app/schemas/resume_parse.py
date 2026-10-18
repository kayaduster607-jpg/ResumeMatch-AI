from pydantic import BaseModel


# ── Sub-structures ─────────────────────────────────────

class BasicInfo(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    gender: str = ""
    age: str = ""
    location: str = ""
    job_title: str = ""
    years_of_experience: str = ""


class EducationItem(BaseModel):
    school: str = ""
    degree: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""


class WorkExperienceItem(BaseModel):
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    achievements: list[str] = []


class ProjectItem(BaseModel):
    name: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    tech_stack: list[str] = []
    description: str = ""
    achievements: list[str] = []


class CertificateItem(BaseModel):
    name: str = ""
    issuer: str = ""
    date: str = ""


class AwardItem(BaseModel):
    name: str = ""
    date: str = ""


class RawQualityCheck(BaseModel):
    is_too_short: bool = False
    missing_projects: bool = False
    missing_skills: bool = False
    missing_work_experience: bool = False
    issues: list[str] = []


# ── Top-level parsed result ────────────────────────────

class ParsedResume(BaseModel):
    basic_info: BasicInfo = BasicInfo()
    education: list[EducationItem] = []
    work_experience: list[WorkExperienceItem] = []
    projects: list[ProjectItem] = []
    skills: list[str] = []
    certificates: list[CertificateItem] = []
    awards: list[AwardItem] = []
    self_evaluation: str = ""
    raw_quality_check: RawQualityCheck = RawQualityCheck()


# ── API response ───────────────────────────────────────

class ResumeParseData(BaseModel):
    resume_id: int
    parsed_json: ParsedResume


class ResumeParseResponse(BaseModel):
    success: bool = True
    data: ResumeParseData
