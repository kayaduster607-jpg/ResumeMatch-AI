"""Tests for resume rewrite quality gates and generic resume-polishing rules."""

from app.schemas.rewrite_resume import RewrittenResumeData, BulletEvidence
from app.services.resume_rewrite_quality import (
    clean_tech_stack_line,
    post_process_rewritten_resume,
    reassess_evidence_chain,
)


def test_clean_tech_stack_line_removes_repo_and_maps_minor_dependencies():
    line = "技术栈：Next.js、TypeScript、pdf-parse、SheetJS、bcryptjs、Repo：https://github.com/a/b"

    result = clean_tech_stack_line(line)

    assert "github" not in result.lower()
    assert "Repo" not in result
    assert "PDF 解析" in result
    assert "Excel / CSV 解析" in result
    assert "密码加密" in result


def test_post_process_adds_strategy_and_quality_gate():
    data = RewrittenResumeData(
        job_title="AI 应用开发实习生",
        full_text="项目经历\n项目A\n技术栈：Python、FastAPI、GitHub：https://github.com/a/b\n- 实现后端接口",
        sections=[],
        evidence_chain=[],
    )

    result = post_process_rewritten_resume(
        data,
        resume_text="项目A 使用 Python 和 FastAPI 实现后端接口",
        resume_parsed={"projects": [{"name": "项目A", "tech_stack": ["Python", "FastAPI"]}]},
        jd_parsed={"title": "AI 应用开发实习生", "required_skills": ["Python"]},
        matched_skills=["Python"],
        missing_skills=[],
        problems=[],
    )

    assert result.rewrite_strategy is not None
    assert result.quality_gate
    assert "github" not in result.full_text.lower()


def test_reassess_evidence_chain_marks_unverified_metrics_high_risk():
    chain = [
        BulletEvidence(
            rewritten_bullet="优化接口性能，响应耗时降低 30%",
            resume_evidence=[],
            jd_evidence=[],
            risk="low",
            fabrication_check="passed",
            need_manual_confirm=False,
        )
    ]

    result = reassess_evidence_chain(chain, resume_text="优化接口性能")

    assert result[0].risk == "high"
    assert result[0].fabrication_check == "warning"
    assert result[0].need_manual_confirm is True
