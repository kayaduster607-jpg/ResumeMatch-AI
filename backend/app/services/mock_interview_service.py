"""Mock interview scoring service.

Evaluates user's interview answer across 5 dimensions:
relevance, technical_depth, structure, evidence, honesty.
"""

import re

from app.schemas.mock_interview import (
    MockInterviewRequest,
    MockInterviewResult,
    DimensionScore,
)

# Dimension weights
WEIGHTS = {
    "relevance": 0.25,
    "technical_depth": 0.25,
    "structure": 0.20,
    "evidence": 0.20,
    "honesty": 0.10,
}


def score_answer(req: MockInterviewRequest) -> MockInterviewResult:
    """Score an interview answer using rule-based heuristics."""
    answer = req.answer.strip()
    question = req.question.strip()

    if not answer:
        return MockInterviewResult(
            score=0,
            level="needs_improvement",
            strengths=[],
            weaknesses=["未提供回答"],
            suggestions=["请提供你的回答内容"],
            improved_answer="",
        )

    # Score each dimension
    dim_scores: list[DimensionScore] = []

    # 1. Relevance
    rel_score, rel_comment = _score_relevance(answer, question)
    dim_scores.append(DimensionScore(dimension="relevance", score=rel_score, comment=rel_comment))

    # 2. Technical depth
    tech_score, tech_comment = _score_technical_depth(answer, req.question_type)
    dim_scores.append(DimensionScore(dimension="technical_depth", score=tech_score, comment=tech_comment))

    # 3. Structure
    struct_score, struct_comment = _score_structure(answer)
    dim_scores.append(DimensionScore(dimension="structure", score=struct_score, comment=struct_comment))

    # 4. Evidence
    evid_score, evid_comment = _score_evidence(answer)
    dim_scores.append(DimensionScore(dimension="evidence", score=evid_score, comment=evid_comment))

    # 5. Honesty
    hon_score, hon_comment = _score_honesty(answer)
    dim_scores.append(DimensionScore(dimension="honesty", score=hon_score, comment=hon_comment))

    # Aggregate
    total = sum(d.score * WEIGHTS[d.dimension] for d in dim_scores)
    total = round(min(100, max(0, total)), 1)

    # Determine level
    if total >= 85:
        level = "excellent"
    elif total >= 70:
        level = "good"
    elif total >= 50:
        level = "fair"
    else:
        level = "needs_improvement"

    # Build feedback
    strengths = _find_strengths(dim_scores)
    weaknesses = _find_weaknesses(dim_scores)
    suggestions = _build_suggestions(dim_scores, req.question_type)
    improved = _build_improved_answer(answer, dim_scores, req.question_type)

    return MockInterviewResult(
        score=total,
        level=level,
        strengths=strengths,
        weaknesses=weaknesses,
        suggestions=suggestions,
        improved_answer=improved,
        dimension_scores=dim_scores,
    )


# ── Dimension scorers ──────────────────────────────────

def _score_relevance(answer: str, question: str) -> tuple[float, str]:
    """Check if the answer addresses the question."""
    # Extract key nouns from question
    q_words = set(re.findall(r"[一-鿿]{2,}|[a-zA-Z]+", question.lower()))
    a_words = set(re.findall(r"[一-鿿]{2,}|[a-zA-Z]+", answer.lower()))

    overlap = q_words & a_words
    if not q_words:
        return 60.0, "无法判断问题关键词"

    ratio = len(overlap) / len(q_words)
    score = min(100, ratio * 120)

    if ratio > 0.5:
        return score, "回答紧扣问题主题"
    elif ratio > 0.3:
        return score, "回答基本相关，但可以更聚焦问题本身"
    else:
        return max(30, score), "回答偏离问题主题，建议先明确回答问题再展开"


def _score_technical_depth(answer: str, q_type: str) -> tuple[float, str]:
    """Evaluate technical depth of the answer."""
    answer_lower = answer.lower()

    # Technical keywords that indicate depth
    depth_indicators = [
        "原理", "底层", "源码", "架构", "设计模式", "算法",
        "性能", "优化", "并发", "分布式", "事务", "索引",
        "缓存", "队列", "协议", "序列化", "反序列化",
        "principle", "architecture", "algorithm", "performance",
        "trade-off", "权衡", "取舍", "对比", "区别",
    ]

    detail_indicators = [
        "例如", "比如", "具体来说", "举个例子", "实际上",
        "for example", "e.g.", "such as", "具体实现",
    ]

    depth_hits = sum(1 for kw in depth_indicators if kw in answer_lower)
    detail_hits = sum(1 for kw in detail_indicators if kw in answer_lower)

    # Length bonus for substantial answers
    length_score = min(30, len(answer) / 20)

    depth_score = min(40, depth_hits * 8)
    detail_score = min(30, detail_hits * 10)

    total = length_score + depth_score + detail_score

    if total >= 70:
        return total, "技术深度较好，涵盖了原理和细节"
    elif total >= 50:
        return total, "有一定技术深度，建议补充更多实现细节和原理"
    else:
        return max(30, total), "技术深度不足，建议解释原理、给出具体实现方案"


def _score_structure(answer: str) -> tuple[float, str]:
    """Evaluate the structure and clarity of the answer."""
    # Check for structural markers
    structure_markers = [
        "首先", "其次", "然后", "最后", "第一", "第二", "第三",
        "首先,", "其次,", "最后,",
        "1.", "2.", "3.", "1、", "2、", "3、",
        "一方面", "另一方面",
        "first", "second", "third", "finally",
    ]

    markers_found = sum(1 for m in structure_markers if m in answer)

    # Check for paragraph breaks
    paragraphs = [p.strip() for p in answer.split("\n") if p.strip()]

    score = 40  # base
    score += min(30, markers_found * 10)
    score += min(20, len(paragraphs) * 5)

    # Penalty for very long single paragraph
    if len(paragraphs) == 1 and len(answer) > 300:
        score -= 10
        return min(100, score), "回答较长但缺少分段，建议分点或分段表述"

    if markers_found >= 3:
        return min(100, score), "结构清晰，层次分明"
    elif markers_found >= 1:
        return min(100, score), "有一定结构，建议使用更明确的分点表述"
    else:
        return max(30, score), "缺少结构化表述，建议用'首先/其次/最后'或分点方式组织回答"


def _score_evidence(answer: str) -> tuple[float, str]:
    """Check if the answer includes concrete examples or evidence."""
    evidence_patterns = [
        r"在.{2,20}项目中",
        r"我.{2,10}(开发|实现|设计|搭建|优化)了",
        r"通过.{2,20}(解决|优化|提升)",
        r"使用.{2,20}(实现|完成|搭建)",
        r"性能.{2,10}(提升|优化|降低)",
        r"\d+\s*[%％]",
        r"\d+\s*(?:万|k|K|QPS|TPS|ms)",
    ]

    hits = sum(1 for p in evidence_patterns if re.search(p, answer))

    if hits >= 3:
        return 90, "结合了具体项目经验和数据"
    elif hits >= 1:
        return 70, "有一些具体例子，建议补充更多项目细节和数据"
    else:
        return 40, "缺少具体证据，建议结合实际项目经历回答"


def _score_honesty(answer: str) -> tuple[float, str]:
    """Check for honesty signals (not over-claiming)."""
    answer_lower = answer.lower()

    # Negative signals (over-claiming)
    overclaim = ["精通", "完全掌握", "非常熟练", "expert", "master"]
    overclaim_hits = sum(1 for kw in overclaim if kw in answer_lower)

    # Positive signals (honesty)
    honest = ["了解", "学习", "接触过", "使用过", "有一定经验", "正在学习"]
    honest_hits = sum(1 for kw in honest if kw in answer_lower)

    # Red flags
    red_flags = ["所有", "全部", "从不犯错", "完美"]
    red_hits = sum(1 for kw in red_flags if kw in answer_lower)

    score = 70  # base
    score += min(20, honest_hits * 7)
    score -= min(20, overclaim_hits * 7)
    score -= min(15, red_hits * 8)

    score = max(30, min(100, score))

    if overclaim_hits > 1:
        return score, "表述略显过度自信，建议用更务实的语言描述能力"
    elif honest_hits > 0:
        return score, "态度诚恳，表述务实"
    else:
        return score, "建议适当展示学习态度，避免过度自信"


# ── Feedback builders ──────────────────────────────────

def _find_strengths(dim_scores: list[DimensionScore]) -> list[str]:
    strengths = []
    for d in dim_scores:
        if d.score >= 75:
            strengths.append(d.comment)
    return strengths[:3]


def _find_weaknesses(dim_scores: list[DimensionScore]) -> list[str]:
    weaknesses = []
    for d in dim_scores:
        if d.score < 60:
            weaknesses.append(d.comment)
    return weaknesses[:3]


def _build_suggestions(dim_scores: list[DimensionScore], q_type: str) -> list[str]:
    suggestions = []
    for d in dim_scores:
        if d.score < 70:
            if d.dimension == "relevance":
                suggestions.append("先用一句话直接回答问题，再展开细节")
            elif d.dimension == "technical_depth":
                suggestions.append("补充技术原理和实现细节，不只是描述功能")
            elif d.dimension == "structure":
                suggestions.append("用'首先/其次/最后'或 1/2/3 分点组织回答")
            elif d.dimension == "evidence":
                suggestions.append("结合具体项目经历和数据来支撑你的回答")
            elif d.dimension == "honesty":
                suggestions.append("保持务实态度，承认不足比过度自信更好")

    if q_type == "technical" and not any("原理" in s for s in suggestions):
        suggestions.append("技术题建议从原理、实现、应用场景三个层面回答")

    return suggestions[:4]


def _build_improved_answer(
    answer: str, dim_scores: list[DimensionScore], q_type: str
) -> str:
    """Suggest an improved answer structure without fabricating content."""
    low_dims = [d.dimension for d in dim_scores if d.score < 60]

    if not low_dims:
        return "回答已经较好，可以在此基础上进一步精炼表达。"

    parts = ["【改进建议】"]

    if "structure" in low_dims:
        parts.append("建议结构: 1) 直接回答问题 2) 解释原理/方案 3) 结合项目举例 4) 总结收获")

    if "evidence" in low_dims:
        parts.append("补充项目证据: 在 [项目名] 中，我使用 [技术] 实现了 [功能]，效果是 [数据]")

    if "technical_depth" in low_dims:
        parts.append("补充技术深度: 解释底层原理、技术选型理由、性能考量")

    if "relevance" in low_dims:
        parts.append("提高相关性: 先用一句话点题，确保每段都和问题相关")

    return "\n".join(parts)
