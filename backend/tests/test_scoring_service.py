"""Tests for the scoring service."""

import pytest
from app.services.scoring_service import (
    compute_scores,
    _score_skills,
    _score_projects,
    _score_requirements,
    _check_education,
    _check_experience,
    _extract_years,
)


# ── Fixtures ───────────────────────────────────────────

def _make_resume(skills=None, projects=None, education=None, work_experience=None, basic_info=None):
    return {
        "skills": skills or [],
        "projects": projects or [],
        "education": education or [],
        "work_experience": work_experience or [],
        "basic_info": basic_info or {},
    }


def _make_jd(required=None, preferred=None, education_requirement="", experience_requirement=""):
    return {
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "education_requirement": education_requirement,
        "experience_requirement": experience_requirement,
        "responsibilities": [],
        "keywords": [],
    }


# ── Skill Scoring ──────────────────────────────────────

class TestScoreSkills:

    def test_perfect_match(self):
        resume = _make_resume(skills=["Python", "FastAPI", "MySQL"])
        jd = _make_jd(required=["Python", "FastAPI", "MySQL"])
        score, reason, matched, missing = _score_skills(resume, jd)
        assert score == 100.0
        assert len(matched) == 3
        assert len(missing) == 0

    def test_partial_match(self):
        resume = _make_resume(skills=["Python", "FastAPI"])
        jd = _make_jd(required=["Python", "FastAPI", "MySQL", "Redis"])
        score, reason, matched, missing = _score_skills(resume, jd)
        assert 40 < score < 80
        assert len(missing) == 2

    def test_no_jd_skills(self):
        resume = _make_resume(skills=["Python"])
        jd = _make_jd()
        score, reason, matched, missing = _score_skills(resume, jd)
        assert score == 70.0  # neutral

    def test_preferred_bonus(self):
        resume = _make_resume(skills=["Python", "Linux"])
        jd = _make_jd(required=["Python"], preferred=["Linux"])
        score, reason, matched, missing = _score_skills(resume, jd)
        # req_ratio = 1.0, pref_bonus = 10
        assert score == 100.0  # min(100, 90 + 10)

    def test_alias_matching(self):
        resume = _make_resume(skills=["py", "fast api"])
        jd = _make_jd(required=["Python", "FastAPI"])
        score, reason, matched, missing = _score_skills(resume, jd)
        assert score == 100.0  # aliases should match

    def test_empty_resume(self):
        resume = _make_resume()
        jd = _make_jd(required=["Python"])
        score, reason, matched, missing = _score_skills(resume, jd)
        assert score < 20
        assert "Python" in missing


# ── Project Scoring ────────────────────────────────────

class TestScoreProjects:

    def test_no_projects(self):
        resume = _make_resume()
        jd = _make_jd(required=["Python"])
        score, reason = _score_projects(resume, jd)
        assert score == 30.0

    def test_good_project(self):
        resume = _make_resume(projects=[{
            "name": "Test Project",
            "tech_stack": ["Python", "FastAPI"],
            "description": "开发了 15 个 RESTful API 接口，使用 Redis 缓存，响应时间优化到 50ms",
            "achievements": ["接口响应时间降低 60%"],
        }])
        jd = _make_jd(required=["Python", "FastAPI", "Redis"])
        score, reason = _score_projects(resume, jd)
        assert score > 60

    def test_weak_project(self):
        resume = _make_resume(projects=[{
            "name": "Weak",
            "tech_stack": [],
            "description": "做了一个项目",
            "achievements": [],
        }])
        jd = _make_jd(required=["Python"])
        score, reason = _score_projects(resume, jd)
        assert score < 50

    def test_quantification_cap(self):
        """Projects without metrics should be capped at 60."""
        resume = _make_resume(projects=[{
            "name": "No Metrics",
            "tech_stack": ["Python"],
            "description": "开发了一个系统" * 10,  # long but no metrics
            "achievements": [],
        }])
        jd = _make_jd(required=["Python"])
        score, reason = _score_projects(resume, jd)
        assert score <= 60


# ── Requirement Scoring ────────────────────────────────

class TestScoreRequirements:

    def test_no_requirements(self):
        resume = _make_resume()
        jd = _make_jd()
        score, reason = _score_requirements(resume, jd)
        assert score == 70.0  # neutral

    def test_education_met(self):
        resume = _make_resume(education=[{"degree": "本科"}])
        jd = _make_jd(education_requirement="本科及以上")
        score, reason = _score_requirements(resume, jd)
        assert score == 100.0

    def test_education_not_met(self):
        resume = _make_resume(education=[{"degree": "大专"}])
        jd = _make_jd(education_requirement="本科及以上")
        score, reason = _score_requirements(resume, jd)
        assert score == 30.0

    def test_education_unknown(self):
        resume = _make_resume()
        jd = _make_jd(education_requirement="本科及以上")
        score, reason = _score_requirements(resume, jd)
        assert score == 60.0  # unknown


class TestCheckEducation:

    def test_bachelor_meets_bachelor(self):
        assert _check_education([{"degree": "本科"}], "本科") is True

    def test_master_meets_bachelor(self):
        assert _check_education([{"degree": "硕士"}], "本科") is True

    def test_associate_fails_bachelor(self):
        assert _check_education([{"degree": "大专"}], "本科") is False

    def test_no_education(self):
        assert _check_education([], "本科") is None

    def test_no_requirement(self):
        assert _check_education([{"degree": "本科"}], "") is None


class TestCheckExperience:

    def test_meets_requirement(self):
        assert _check_experience(3, "2年以上经验") is True

    def test_below_requirement(self):
        assert _check_experience(1, "3年以上经验") is False

    def test_unknown_years(self):
        assert _check_experience(None, "2年") is None

    def test_no_requirement(self):
        assert _check_experience(3, "") is None


class TestExtractYears:

    def test_from_basic_info(self):
        resume = _make_resume(basic_info={"years_of_experience": "3"})
        assert _extract_years(resume) == 3

    def test_from_work_experience(self):
        resume = _make_resume(work_experience=[
            {"start_date": "2022.01", "end_date": "2024.01"}
        ])
        years = _extract_years(resume)
        assert years == 2

    def test_no_experience(self):
        resume = _make_resume()
        assert _extract_years(resume) is None


# ── Full Pipeline ──────────────────────────────────────

class TestComputeScores:

    def test_returns_scoring_result(self):
        resume = _make_resume(
            skills=["Python", "FastAPI", "MySQL"],
            projects=[{
                "name": "Test",
                "tech_stack": ["Python"],
                "description": "开发了 API 接口，性能提升 30%",
                "achievements": [],
            }],
            education=[{"degree": "本科"}],
        )
        jd = _make_jd(
            required=["Python", "FastAPI"],
            education_requirement="本科",
        )
        result = compute_scores(resume, jd, "resume text", "jd text")

        assert 0 <= result.total_score <= 100
        assert result.score_detail.skill_score >= 0
        assert result.score_detail.project_score >= 0
        assert result.score_detail.semantic_score >= 0
        assert result.score_detail.requirement_score >= 0
        assert isinstance(result.matched_skills, list)
        assert isinstance(result.missing_skills, list)

    def test_empty_inputs(self):
        resume = _make_resume()
        jd = _make_jd()
        result = compute_scores(resume, jd, "", "")
        assert 0 <= result.total_score <= 100
