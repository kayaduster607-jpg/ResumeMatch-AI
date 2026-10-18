import pytest
from app.services.skill_normalizer import normalize_skill, normalize_skills


class TestNormalizeSkill:
    """Tests for single skill normalization."""

    def test_exact_match(self):
        result = normalize_skill("Python")
        assert result.name == "Python"
        assert result.category == "programming_language"
        assert result.confidence >= 0.95

    def test_case_insensitive(self):
        result = normalize_skill("python")
        assert result.name == "Python"

    def test_common_alias(self):
        result = normalize_skill("py")
        assert result.name == "Python"
        assert result.confidence >= 0.95

    def test_framework_alias(self):
        result = normalize_skill("react.js")
        assert result.name == "React"
        assert result.category == "frontend"

    def test_framework_alias_vuejs(self):
        result = normalize_skill("Vue.js")
        assert result.name == "Vue"

    def test_backend_alias(self):
        result = normalize_skill("fast api")
        assert result.name == "FastAPI"
        assert result.category == "backend"

    def test_database_alias(self):
        result = normalize_skill("postgres")
        assert result.name == "PostgreSQL"
        assert result.category == "database"

    def test_devops_alias(self):
        result = normalize_skill("k8s")
        assert result.name == "Kubernetes"
        assert result.category == "devops"

    def test_ai_alias(self):
        result = normalize_skill("LLM")
        assert result.name == "LLM"
        assert result.category == "ai_ml"

    def test_chinese_skill(self):
        result = normalize_skill("大模型")
        assert result.name == "LLM"
        assert result.category == "ai_ml"

    def test_vector_db_alias(self):
        result = normalize_skill("向量数据库")
        assert result.category == "ai_ml"

    def test_unknown_skill(self):
        result = normalize_skill("SomeUnknownTech")
        assert result.name == "Someunknowntech"  # title-cased
        assert result.category == "other"
        assert result.confidence == 0.3

    def test_empty_string(self):
        result = normalize_skill("")
        assert result.category == "other"
        assert result.confidence == 0.0

    def test_whitespace_handling(self):
        result = normalize_skill("  Python  ")
        assert result.name == "Python"

    def test_js_alias(self):
        result = normalize_skill("JS")
        assert result.name == "JavaScript"

    def test_ts_alias(self):
        result = normalize_skill("ts")
        assert result.name == "TypeScript"


class TestNormalizeSkills:
    """Tests for batch normalization with deduplication."""

    def test_basic_batch(self):
        results = normalize_skills(["Python", "MySQL", "Docker"])
        assert len(results) == 3
        names = [r.name for r in results]
        assert "Python" in names
        assert "MySQL" in names
        assert "Docker" in names

    def test_dedup_same_canonical(self):
        results = normalize_skills(["Python", "python", "py"])
        assert len(results) == 1
        assert results[0].name == "Python"

    def test_dedup_keeps_highest_confidence(self):
        results = normalize_skills(["py", "Python"])
        assert len(results) == 1
        # Exact "Python" match should have higher confidence
        assert results[0].confidence >= 0.95

    def test_different_canonicals_kept(self):
        results = normalize_skills(["JS", "JavaScript", "TypeScript", "ts"])
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"JavaScript", "TypeScript"}

    def test_empty_list(self):
        results = normalize_skills([])
        assert results == []

    def test_empty_strings_filtered(self):
        results = normalize_skills(["", "  ", "Python"])
        assert len(results) == 1

    def test_preserves_raw(self):
        results = normalize_skills(["py"])
        assert results[0].raw == "py"

    def test_mixed_known_unknown(self):
        results = normalize_skills(["Python", "SomeRandomThing"])
        assert len(results) == 2
        names = {r.name for r in results}
        assert "Python" in names

    def test_full_pipeline(self):
        """Simulate a real resume skill list."""
        raw_skills = [
            "Python", "python", "py",
            "React", "react.js", "ReactJS",
            "MySQL", "mysql",
            "Docker", "docker",
            "FastAPI", "fast api",
            "大模型", "LLM",
        ]
        results = normalize_skills(raw_skills)
        names = sorted([r.name for r in results])
        expected = sorted(["Python", "React", "MySQL", "Docker", "FastAPI", "LLM"])
        assert names == expected
