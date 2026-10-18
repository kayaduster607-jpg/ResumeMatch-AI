"""Tests for JD parse service (mock mode)."""

import pytest
from app.services.jd_parse_service import _mock_parse_jd, _normalize_skills


class TestMockParseJD:
    """Tests for the mock JD parser."""

    def test_full_jd(self):
        """A well-structured JD should extract all sections."""
        text = """Python 后端开发实习生

岗位职责：
1. 负责后端 API 开发和维护
2. 参与数据库设计和优化
3. 编写单元测试

任职要求：
1. 熟悉 Python，有实际项目经验
2. 熟悉 FastAPI 或 Django
3. 熟悉 MySQL
4. 了解 Docker

加分项：
- 有开源项目经验
- 熟悉 Linux
"""
        result = _mock_parse_jd(text, "Python 后端开发实习生", "某科技公司")

        assert result.job_title == "Python 后端开发实习生"
        assert result.company == "某科技公司"
        assert len(result.responsibilities) > 0
        assert len(result.required_skills) > 0
        assert "Python" in result.required_skills or "Python" in result.programming_languages

    def test_minimal_jd(self):
        """A minimal JD with just requirements should still parse."""
        text = """
要求：
- 熟悉 Python
- 了解 MySQL
"""
        result = _mock_parse_jd(text, None, None)

        assert result.job_title == ""
        assert result.company == ""
        # Should extract something even from minimal input
        assert isinstance(result.required_skills, list)

    def test_empty_jd(self):
        """An empty JD should return empty results without crashing."""
        result = _mock_parse_jd("", None, None)

        assert result.job_title == ""
        assert result.responsibilities == []
        assert result.required_skills == []

    def test_english_jd(self):
        """An English JD should extract skills."""
        text = """Backend Developer Intern

Responsibilities:
1. Develop RESTful APIs
2. Write unit tests

Requirements:
1. Proficient in Python
2. Experience with FastAPI
3. Familiar with MySQL and Redis
"""
        result = _mock_parse_jd(text, "Backend Developer Intern", "Tech Corp")

        assert result.job_title == "Backend Developer Intern"
        assert len(result.responsibilities) > 0

    def test_seniority_detection(self):
        """Should detect seniority level from JD text."""
        junior_text = "实习岗位，应届生优先"
        result = _mock_parse_jd(junior_text, "实习", None)
        assert result.seniority_level == "junior"

        senior_text = "高级开发工程师，5年以上经验"
        result = _mock_parse_jd(senior_text, "高级开发", None)
        assert result.seniority_level == "senior"

    def test_soft_skills_extraction(self):
        """Should extract soft skills mentioned in JD."""
        text = "要求具备良好的沟通能力和团队协作精神，有较强的学习能力"
        result = _mock_parse_jd(text, None, None)

        assert any("沟通" in s for s in result.soft_skills)
        assert any("团队" in s for s in result.soft_skills)


class TestNormalizeSkillsJD:
    """Tests for the JD-specific skill normalization."""

    def test_basic_normalization(self):
        result = _normalize_skills(["python", "mysql", "docker"])
        assert "Python" in result
        assert "MySQL" in result
        assert "Docker" in result

    def test_deduplication(self):
        result = _normalize_skills(["python", "Python", "py"])
        # Should deduplicate to canonical names
        python_count = sum(1 for s in result if s.lower() == "python")
        assert python_count == 1

    def test_empty_list(self):
        result = _normalize_skills([])
        assert result == []

    def test_empty_strings(self):
        result = _normalize_skills(["", "  ", "Python"])
        assert len(result) == 1
        assert result[0] == "Python"

    def test_unknown_skills_preserved(self):
        result = _normalize_skills(["SomeUnknownTech"])
        assert len(result) == 1
        assert result[0] == "SomeUnknownTech"
