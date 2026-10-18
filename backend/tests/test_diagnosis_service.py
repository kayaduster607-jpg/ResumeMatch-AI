"""Tests for the diagnosis service."""

import pytest
from app.services.diagnosis_service import (
    diagnose,
    _check_missing_required_skill,
    _check_weak_project_description,
    _check_lack_of_metrics,
    _check_skill_not_reflected,
    _check_format_issue,
    _check_vague_action,
    _check_unclear_role,
)


# ── Fixtures ───────────────────────────────────────────

def _make_resume(skills=None, projects=None, basic_info=None):
    return {
        "skills": skills or [],
        "projects": projects or [],
        "basic_info": basic_info or {},
        "education": [],
        "work_experience": [],
    }


def _make_jd(required=None, preferred=None):
    return {
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "responsibilities": [],
        "keywords": [],
    }


# ── Missing Required Skill ─────────────────────────────

class TestMissingRequiredSkill:

    def test_no_missing(self):
        issues = _check_missing_required_skill(_make_jd(), [])
        assert issues == []

    def test_one_missing(self):
        issues = _check_missing_required_skill(_make_jd(), ["Docker"])
        assert len(issues) == 1
        assert issues[0].type == "missing_required_skill"
        assert issues[0].severity == "high"
        assert "Docker" in issues[0].title

    def test_cap_at_five(self):
        missing = ["A", "B", "C", "D", "E", "F", "G"]
        issues = _check_missing_required_skill(_make_jd(), missing)
        assert len(issues) == 5


# ── Weak Project Description ───────────────────────────

class TestWeakProjectDescription:

    def test_empty_description(self):
        resume = _make_resume(projects=[{"name": "Test", "description": ""}])
        issues = _check_weak_project_description(resume)
        assert len(issues) == 1
        assert issues[0].severity == "high"

    def test_short_description(self):
        resume = _make_resume(projects=[{"name": "Test", "description": "做了项目"}])
        issues = _check_weak_project_description(resume)
        assert len(issues) == 1
        assert issues[0].severity == "medium"

    def test_good_description(self):
        resume = _make_resume(projects=[{
            "name": "Test",
            "description": "使用 FastAPI 开发了用户认证系统，实现了 JWT Token 管理和 Redis 缓存，支持 10万用户并发登录"
        }])
        issues = _check_weak_project_description(resume)
        assert len(issues) == 0

    def test_no_projects(self):
        issues = _check_weak_project_description(_make_resume())
        assert issues == []


# ── Lack of Metrics ────────────────────────────────────

class TestLackOfMetrics:

    def test_no_projects(self):
        issues = _check_lack_of_metrics(_make_resume())
        assert issues == []

    def test_has_metrics(self):
        resume = _make_resume(projects=[{
            "name": "Test",
            "description": "接口响应时间降低 60%，日均处理 5万请求",
            "achievements": [],
        }])
        issues = _check_lack_of_metrics(resume)
        assert len(issues) == 0

    def test_no_metrics(self):
        resume = _make_resume(projects=[
            {"name": "A", "description": "开发了系统", "achievements": []},
            {"name": "B", "description": "做了功能", "achievements": []},
        ])
        issues = _check_lack_of_metrics(resume)
        assert len(issues) == 1
        assert issues[0].type == "lack_of_metrics"


# ── Skill Not Reflected ────────────────────────────────

class TestSkillNotReflected:

    def test_all_reflected(self):
        resume = _make_resume(
            skills=["Python", "FastAPI"],
            projects=[{"tech_stack": ["Python", "FastAPI"], "description": "使用 Python 和 FastAPI 开发"}]
        )
        issues = _check_skill_not_reflected(resume, ["Python", "FastAPI"])
        assert len(issues) == 0

    def test_some_not_reflected(self):
        resume = _make_resume(
            skills=["Python", "Docker"],
            projects=[{"tech_stack": ["Python"], "description": "Python 项目"}]
        )
        issues = _check_skill_not_reflected(resume, ["Python", "Docker"])
        assert len(issues) == 1
        assert "Docker" in issues[0].evidence

    def test_no_matched_skills(self):
        issues = _check_skill_not_reflected(_make_resume(), [])
        assert issues == []


# ── Format Issue ───────────────────────────────────────

class TestFormatIssue:

    def test_missing_name(self):
        resume = _make_resume(basic_info={"phone": "13800138000"})
        issues = _check_format_issue(resume)
        assert any(i.type == "format_issue" and "姓名" in i.title for i in issues)

    def test_missing_contact(self):
        resume = _make_resume(basic_info={"name": "张三"})
        issues = _check_format_issue(resume)
        assert any(i.type == "format_issue" and "联系方式" in i.title for i in issues)

    def test_missing_skills_section(self):
        resume = _make_resume(skills=[], basic_info={"name": "张三", "phone": "13800138000"})
        issues = _check_format_issue(resume)
        assert any(i.type == "format_issue" and "技能" in i.title for i in issues)

    def test_complete_resume(self):
        resume = _make_resume(
            skills=["Python"],
            basic_info={"name": "张三", "phone": "13800138000", "email": "test@test.com"}
        )
        issues = _check_format_issue(resume)
        assert len(issues) == 0


# ── Vague Action ───────────────────────────────────────

class TestVagueAction:

    def test_vague_responsible(self):
        resume = _make_resume(projects=[{"name": "Test", "description": "负责开发"}])
        issues = _check_vague_action(resume)
        assert len(issues) == 1
        assert issues[0].type == "vague_action"

    def test_specific_action(self):
        resume = _make_resume(projects=[{
            "name": "Test",
            "description": "设计并实现了基于 JWT 的用户认证系统，支持 OAuth2.0 第三方登录"
        }])
        issues = _check_vague_action(resume)
        assert len(issues) == 0


# ── Unclear Role ───────────────────────────────────────

class TestUnclearRole:

    def test_no_role(self):
        resume = _make_resume(projects=[{"name": "Test", "role": ""}])
        issues = _check_unclear_role(resume)
        assert len(issues) == 1
        assert "未说明" in issues[0].title

    def test_clear_role(self):
        resume = _make_resume(projects=[{"name": "Test", "role": "核心后端开发，负责 API 设计与实现"}])
        issues = _check_unclear_role(resume)
        assert len(issues) == 0


# ── Full Diagnosis ─────────────────────────────────────

class TestDiagnose:

    def test_returns_list(self):
        resume = _make_resume(
            skills=["Python"],
            projects=[{"name": "Test", "tech_stack": ["Python"], "description": "负责开发", "role": ""}],
            basic_info={"name": "张三", "phone": "13800138000"},
        )
        jd = _make_jd(required=["Python", "Docker"])
        issues = diagnose(resume, jd, ["Python"], ["Docker"])
        assert isinstance(issues, list)
        assert len(issues) > 0

    def test_empty_inputs(self):
        issues = diagnose(_make_resume(), _make_jd(), [], [])
        assert isinstance(issues, list)

    def test_issue_has_required_fields(self):
        resume = _make_resume(
            projects=[{"name": "Test", "description": "", "tech_stack": [], "role": ""}],
            basic_info={},
        )
        jd = _make_jd(required=["Docker"])
        issues = diagnose(resume, jd, [], ["Docker"])
        for issue in issues:
            assert issue.type
            assert issue.severity in ("high", "medium", "low")
            assert issue.title
            assert issue.evidence
            assert issue.reason
            assert issue.suggestion
