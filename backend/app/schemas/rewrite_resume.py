from pydantic import BaseModel, Field
from typing import Optional, Literal


class ResumeSection(BaseModel):
    """A section of the rewritten resume."""
    title: str
    content: str


class EvidenceItem(BaseModel):
    """A single piece of evidence linking a rewritten claim to its source.

    source_type distinguishes resume facts (proof the candidate did something)
    from JD requirements (what the job wants — relevant but not proof of experience).
    """
    source: str = ""          # e.g. "project.ResumeMatch-AI.backend"
    source_type: Literal[
        "resume_project",
        "resume_skill",
        "resume_work_experience",
        "resume_education",
        "jd_requirement",
        "jd_preferred",
        "system_rule",
    ] = "system_rule"
    field: str = ""           # e.g. "FastAPI, SQLAlchemy, Pydantic"
    confidence: float = 0.0   # 0.0 - 1.0


class BulletEvidence(BaseModel):
    """Evidence chain for a single rewritten bullet point.

    Evidence is split into two categories:
    - resume_evidence: facts from the candidate's actual resume (proves "I did this")
    - jd_evidence: requirements from the job description (shows "this is what the job needs")

    Risk assessment is driven primarily by resume_evidence.
    JD evidence alone cannot prove the candidate did something — it only indicates
    what the job requires. A bullet supported only by JD evidence gets high risk
    and fabrication_check=warning.
    """
    rewritten_bullet: str = ""
    resume_evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Evidence from the candidate's actual resume (projects, skills, work experience)"
    )
    jd_evidence: list[EvidenceItem] = Field(
        default_factory=list,
        description="Evidence from the job description requirements (what the job needs)"
    )
    risk: Literal["low", "medium", "high"] = "low"
    fabrication_check: Literal["passed", "warning", "failed"] = "passed"
    need_manual_confirm: bool = Field(
        default=False,
        description="True when the rewritten bullet needs human review before use"
    )


class RewriteStrategy(BaseModel):
    """Transparent strategy used by the resume rewrite engine.

    This makes the rewrite process auditable instead of a black-box text generation.
    """
    target_role: str = ""
    role_requirements: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)
    section_order: list[str] = Field(default_factory=list)
    project_style: str = "项目简介 → 技术栈 → 技术亮点"
    tech_stack_rules: list[str] = Field(default_factory=list)
    quantification_rules: list[str] = Field(default_factory=list)
    tone_rules: list[str] = Field(default_factory=list)
    omitted_or_compressed: list[str] = Field(default_factory=list)


class RewriteQualityGateItem(BaseModel):
    """One deterministic quality check performed after LLM/rule rewriting."""
    name: str = ""
    status: Literal["passed", "warning", "failed"] = "passed"
    message: str = ""


class RewrittenResumeData(BaseModel):
    """Structured rewritten resume with evidence chain."""
    job_title: str = ""
    target_company: str = ""
    summary: str = ""  # Professional summary tailored to JD
    sections: list[ResumeSection] = []
    highlights: list[str] = []  # Key changes / improvements
    full_text: str = ""  # Complete plain text version
    changes_summary: str = ""  # Summary of what was changed and why
    evidence_chain: list[BulletEvidence] = Field(
        default_factory=list,
        description="Evidence chain binding each rewritten bullet to resume facts and JD requirements"
    )
    rewrite_strategy: Optional[RewriteStrategy] = Field(
        default=None,
        description="Auditable rewrite strategy generated from JD requirements and candidate evidence"
    )
    quality_gate: list[RewriteQualityGateItem] = Field(
        default_factory=list,
        description="Deterministic quality checks for direct-delivery format, tech stack hygiene, tone, metrics and evidence"
    )


class RewriteResumeRequest(BaseModel):
    """Request to generate a rewritten resume."""
    task_id: int


class RewriteResumeResponse(BaseModel):
    """Response for rewritten resume."""
    id: int
    task_id: int
    rewritten_text: str
    rewritten_json: Optional[RewrittenResumeData] = None
    edited_text: Optional[str] = None
    source: str


class SaveEditedResumeRequest(BaseModel):
    """Save user edits to the rewritten resume."""
    edited_text: str
