"""Interview question generation service.

Generates targeted interview questions based on resume, JD, and matching results.
Distribution: technical 3, project 3, gap_based 2, scenario 1, behavioral 1.
"""

import json
import random
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.analysis_task import AnalysisTask, TaskStatus
from app.models.resume import Resume
from app.models.job_description import JobDescription
from app.schemas.interview import InterviewQuestionItem, InterviewQuestionsData
from app.services.llm_client import get_llm_client, is_real_llm_enabled

# Question distribution
DISTRIBUTION = {
    "technical": 5,
    "project": 4,
    "gap_based": 3,
    "scenario": 2,
    "behavioral": 1,
}


def generate_interview_questions(task_id: int, db: Session) -> InterviewQuestionsData:
    """Generate targeted interview questions for a completed analysis.

    DeepSeek/OpenAI-compatible LLM is used first when configured.  The old
    rule templates are retained only as a fallback when strict mode is off.
    """
    task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
    if task is None:
        raise AppException(f"分析记录 {task_id} 不存在。", code="NOT_FOUND", status_code=404)
    if task.status != TaskStatus.completed:
        raise AppException("请先完成分析匹配。", code="NOT_COMPLETED")

    resume = db.query(Resume).filter(Resume.id == task.resume_id).first()
    jd = db.query(JobDescription).filter(JobDescription.id == task.jd_id).first()
    if not resume or not jd:
        raise AppException("简历或岗位不存在。", code="DATA_MISSING")

    resume_parsed = _safe_json(resume.parsed_json)
    jd_parsed = _safe_json(jd.parsed_json)

    from app.models.match_report import MatchReport
    report = db.query(MatchReport).filter(MatchReport.task_id == task_id).first()
    missing_skills = _safe_json_list(report.missing_skills_json if report else None)
    matched_skills = _safe_json_list(report.matched_skills_json if report else None)

    ai_result = _try_generate_ai_questions(
        resume_text=resume.raw_text or "",
        jd_text=jd.raw_text or "",
        resume_parsed=resume_parsed,
        jd_parsed=jd_parsed,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
    )
    if ai_result:
        return ai_result

    questions: list[InterviewQuestionItem] = []
    seen_questions: set[str] = set()

    def add_question(q: InterviewQuestionItem) -> None:
        if q.question not in seen_questions:
            seen_questions.add(q.question)
            questions.append(q)

    for q in _generate_technical(jd_parsed, matched_skills):
        add_question(q)
    for q in _generate_project(resume_parsed):
        add_question(q)
    for q in _generate_gap_based(missing_skills):
        add_question(q)
    for q in _generate_scenario(jd_parsed):
        add_question(q)
    for q in _generate_behavioral():
        add_question(q)

    return InterviewQuestionsData(questions=questions[:15])


def _try_generate_ai_questions(
    resume_text: str,
    jd_text: str,
    resume_parsed: dict,
    jd_parsed: dict,
    matched_skills: list[str],
    missing_skills: list[str],
) -> Optional[InterviewQuestionsData]:
    if not is_real_llm_enabled():
        return None
    system = """你是一位中文技术面试官和招聘面试教练。请基于候选人简历、目标JD、匹配技能和缺口，生成10道高质量面试题。
要求：
1. 问题必须具体到候选人的项目或JD要求，不能空泛。
2. 至少3道技术题、3道项目深挖题、2道缺口追问题、1道场景题、1道行为题。
3. 每题给出为什么问、参考回答要点、关联简历证据或JD要求。
4. 只返回JSON。"""
    user = f"""
JD原文：
{jd_text[:5000]}

简历原文：
{resume_text[:7000]}

JD解析：
{json.dumps(jd_parsed, ensure_ascii=False)[:3000]}

简历解析：
{json.dumps(resume_parsed, ensure_ascii=False)[:3000]}

已匹配技能：{matched_skills}
缺失/风险技能：{missing_skills}

请返回JSON：
{{
  "questions": [
    {{
      "question_type": "technical/project/gap_based/scenario/behavioral",
      "difficulty": "easy/medium/hard",
      "question": "具体问题",
      "why_ask": "为什么问这题",
      "reference_answer": "候选人应该回答的要点",
      "related_resume_evidence": "关联的简历证据，没有则空字符串",
      "related_jd_requirement": "关联的JD要求，没有则空字符串"
    }}
  ]
}}
"""
    try:
        data = get_llm_client().chat_json(system, user, temperature=0.22)
        raw_questions = data.get("questions") or []
        questions: list[InterviewQuestionItem] = []
        seen: set[str] = set()
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or "").strip()
            if not question or question in seen:
                continue
            seen.add(question)
            questions.append(InterviewQuestionItem(
                question_type=str(item.get("question_type") or "technical"),
                difficulty=str(item.get("difficulty") or "medium"),
                question=question,
                why_ask=str(item.get("why_ask") or "考察候选人与目标岗位的匹配度。"),
                reference_answer=str(item.get("reference_answer") or "应结合简历项目和JD要求回答。"),
                related_resume_evidence=str(item.get("related_resume_evidence") or ""),
                related_jd_requirement=str(item.get("related_jd_requirement") or ""),
            ))
            if len(questions) >= 10:
                break
        if len(questions) >= 6:
            return InterviewQuestionsData(questions=questions[:15])
        raise RuntimeError("DeepSeek返回的面试题数量不足或格式不完整。")
    except Exception as exc:
        if get_settings().LLM_STRICT_MODE:
            raise AppException(f"DeepSeek 面试题生成失败：{exc}", code="LLM_INTERVIEW_QUESTION_FAILED", status_code=500) from exc
        return None


def _safe_json(text: Optional[str]) -> dict:
    if not text:
        return {}
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _safe_json_list(text: Optional[str]) -> list[str]:
    if not text:
        return []
    try:
        value = json.loads(text)
        if isinstance(value, list):
            return [str(x) for x in value if str(x).strip()]
    except Exception:
        pass
    return []


def _generate_technical(jd_parsed: dict, matched_skills: list[str]) -> list[InterviewQuestionItem]:
    """Generate technical questions from JD required skills."""
    questions = []
    required = jd_parsed.get("required_skills", [])[:5]

    templates = {
        "python": [
            ("请解释 Python 中 GIL 的作用及其对多线程编程的影响", "medium"),
            ("Python 中 list 和 tuple 的区别是什么？什么场景下用哪个？", "easy"),
            ("请解释 Python 的装饰器原理，并写一个简单的计时装饰器", "medium"),
            ("Python 中 async/await 的工作原理是什么？什么场景下用？", "hard"),
            ("请解释 Python 的内存管理机制和垃圾回收", "hard"),
        ],
        "mysql": [
            ("请解释 MySQL 中索引的原理，以及如何优化慢查询", "medium"),
            ("MySQL 中 InnoDB 和 MyISAM 的区别是什么？", "easy"),
            ("请解释事务的 ACID 特性，并举例说明", "medium"),
            ("MySQL 主从复制是如何工作的？读写分离有哪些注意事项？", "hard"),
        ],
        "redis": [
            ("Redis 有哪些数据结构？分别适合什么场景？", "easy"),
            ("请解释 Redis 缓存穿透、缓存击穿、缓存雪崩的区别和解决方案", "hard"),
            ("Redis 如何实现分布式锁？有哪些注意事项？", "hard"),
            ("Redis 的持久化机制 RDB 和 AOF 有什么区别？", "medium"),
        ],
        "docker": [
            ("请解释 Docker 的核心概念：镜像、容器、仓库", "easy"),
            ("Dockerfile 中 CMD 和 ENTRYPOINT 的区别是什么？", "medium"),
            ("如何优化 Docker 镜像大小？", "medium"),
        ],
        "fastapi": [
            ("FastAPI 的依赖注入系统是如何工作的？", "medium"),
            ("FastAPI 如何实现请求参数校验？和 Flask 有什么不同？", "easy"),
            ("FastAPI 中如何处理全局异常和中间件？", "medium"),
        ],
        "react": [
            ("React 中 state 和 props 的区别是什么？", "easy"),
            ("请解释 React Hooks 的原理，useEffect 的依赖数组如何影响执行？", "medium"),
            ("React 中虚拟 DOM 的工作原理是什么？", "medium"),
            ("什么是 React 的性能优化策略？用过 useMemo/useCallback 吗？", "hard"),
        ],
        "javascript": [
            ("请解释 JavaScript 的事件循环机制", "medium"),
            ("JavaScript 中闭包是什么？有什么实际应用场景？", "medium"),
            ("请解释 Promise 和 async/await 的关系", "easy"),
        ],
        "typescript": [
            ("TypeScript 中 interface 和 type 的区别是什么？", "easy"),
            ("请解释 TypeScript 的泛型，并举例说明使用场景", "medium"),
        ],
        "node.js": [
            ("Node.js 的事件驱动和非阻塞 I/O 是如何工作的？", "medium"),
            ("Express 中间件的执行顺序是怎样的？", "easy"),
        ],
        "微服务": [
            ("微服务架构中如何保证数据一致性？", "hard"),
            ("服务间通信有哪些方式？各自的优缺点？", "medium"),
            ("微服务架构中如何实现服务发现和负载均衡？", "hard"),
        ],
        "linux": [
            ("常用的 Linux 性能排查命令有哪些？", "easy"),
            ("如何查看进程占用的端口和资源？", "easy"),
        ],
        "git": [
            ("Git 中 merge 和 rebase 的区别是什么？", "easy"),
            ("如何解决 Git 合并冲突？", "easy"),
        ],
        "kafka": [
            ("Kafka 如何保证消息不丢失？", "hard"),
            ("请解释 Kafka 的消费者组机制", "medium"),
        ],
        "elasticsearch": [
            ("Elasticsearch 的倒排索引原理是什么？", "medium"),
            ("ES 中如何优化搜索性能？", "medium"),
        ],
    }

    # Match skills to templates
    used = 0
    for skill in required:
        if used >= 5:
            break
        skill_lower = skill.lower()
        for key, q_list in templates.items():
            if key in skill_lower:
                q = random.choice(q_list)
                questions.append(InterviewQuestionItem(
                    question_type="technical",
                    difficulty=q[1],
                    question=q[0],
                    why_ask=f"考察 {skill} 技术基础，这是 JD 要求的核心技能",
                    reference_answer=f"应涵盖 {skill} 的核心概念、原理和实际应用场景",
                    related_jd_requirement=f"JD 要求: {skill}",
                ))
                used += 1
                break

    # Fallback generic technical questions
    generic = [
        ("请介绍你最熟悉的一个技术栈，包括它的优势和适用场景", "easy", "考察技术广度和深度"),
        ("你在开发中遇到过最复杂的技术问题是什么？如何解决的？", "medium", "考察问题解决能力"),
        ("请解释 RESTful API 的设计原则", "easy", "考察 API 设计基础"),
        ("请解释 MVC/MVVM 设计模式，以及它们的区别", "medium", "考察架构设计理解"),
        ("什么是 CI/CD？你在项目中是如何实践的？", "medium", "考察工程化能力"),
        ("请解释 OOP 的三大特性，并举例说明", "easy", "考察编程基础"),
        ("如何评估一个技术方案的好坏？有哪些考量维度？", "hard", "考察技术决策能力"),
    ]
    while len(questions) < 5:
        q = random.choice(generic)
        questions.append(InterviewQuestionItem(
            question_type="technical",
            difficulty=q[1],
            question=q[0],
            why_ask=q[2],
            reference_answer="应结合实际项目经验回答",
        ))

    return questions


def _generate_project(resume_parsed: dict) -> list[InterviewQuestionItem]:
    """Generate project deep-dive questions from resume projects."""
    questions = []
    projects = resume_parsed.get("projects", [])

    if not projects:
        generic = [
            ("请介绍你做过的最有技术挑战的项目", "medium", "了解项目经验和技术深度"),
            ("你在项目中遇到过最大的困难是什么？如何解决的？", "medium", "考察问题解决能力"),
            ("如果让你重新做这个项目，你会如何改进？", "medium", "考察复盘和技术视野"),
            ("请描述一个你从0到1主导的项目，包括技术选型过程", "medium", "考察项目推动能力"),
            ("你如何衡量项目的技术成功？有哪些关键指标？", "medium", "考察工程思维"),
        ]
        for q in generic:
            questions.append(InterviewQuestionItem(
                question_type="project",
                difficulty=q[1],
                question=q[0],
                why_ask=q[2],
                reference_answer="应结合具体项目细节回答",
            ))
        return questions

    for proj in projects[:3]:
        name = proj.get("name", "项目")
        tech = proj.get("tech_stack", [])
        tech_str = "、".join(tech[:3]) if tech else "相关技术"

        questions.append(InterviewQuestionItem(
            question_type="project",
            difficulty="medium",
            question=f"请详细介绍 [{name}] 项目：你负责什么？用了什么技术方案？遇到什么挑战？",
            why_ask=f"深入了解 [{name}] 项目的实际贡献和技术深度",
            reference_answer=f"应涵盖: 项目背景、你的角色、技术选型理由、核心实现、遇到的问题和解决方案",
            related_resume_evidence=f"简历项目: {name}，技术栈: {tech_str}",
        ))

    return questions


def _generate_gap_based(missing_skills: list[str]) -> list[InterviewQuestionItem]:
    """Generate questions for missing skills to assess learning ability."""
    questions = []

    templates = {
        "docker": ("你了解 Docker 吗？如果让你用 Docker 部署一个 Python Web 服务，你会怎么做？", "medium"),
        "kubernetes": ("你了解 Kubernetes 吗？能简单解释 Pod、Service、Deployment 的概念吗？", "hard"),
        "redis": ("你了解 Redis 吗？在什么场景下会使用缓存？", "easy"),
        "kafka": ("你了解消息队列吗？什么场景下需要用到 Kafka/RabbitMQ？", "medium"),
        "微服务": ("你了解微服务架构吗？和单体架构相比有什么优缺点？", "medium"),
        "elasticsearch": ("你了解 Elasticsearch 吗？什么场景会用到全文搜索？", "medium"),
        "typescript": ("你对 TypeScript 了解多少？它和 JavaScript 相比有什么优势？", "easy"),
        "react": ("你对 React 了解多少？组件化开发有什么好处？", "easy"),
        "mongodb": ("你了解 MongoDB 吗？它和 MySQL 的根本区别是什么？", "easy"),
        "cicd": ("你了解 CI/CD 流程吗？自动化部署的核心价值是什么？", "medium"),
        "linux": ("你对 Linux 常用命令掌握到什么程度？", "easy"),
        "git": ("你平时使用 Git 做版本管理吗？团队协作的分支策略是怎样的？", "easy"),
    }

    for skill in missing_skills[:2]:
        matched_template = None
        for key, tpl in templates.items():
            if key in skill.lower():
                matched_template = tpl
                break

        if matched_template:
            questions.append(InterviewQuestionItem(
                question_type="gap_based",
                difficulty=matched_template[1],
                question=matched_template[0],
                why_ask=f"JD 要求 {skill}，但简历中未体现，考察学习意愿和基础了解",
                reference_answer=f"即使没有实际经验，也应展示基本了解和学习意愿",
                related_jd_requirement=f"JD 要求: {skill}",
            ))
        else:
            questions.append(InterviewQuestionItem(
                question_type="gap_based",
                difficulty="medium",
                question=f"JD 要求具备 {skill} 的经验，你目前了解多少？有计划学习吗？",
                why_ask=f"JD 要求 {skill}，简历中未体现，考察学习态度",
                reference_answer="诚实回答当前水平，展示学习计划和主动性",
                related_jd_requirement=f"JD 要求: {skill}",
            ))

    return questions


def _generate_scenario(jd_parsed: dict) -> list[InterviewQuestionItem]:
    """Generate scenario-based questions related to the JD."""
    responsibilities = jd_parsed.get("responsibilities", [])
    # Clean title: remove salary/location/etc, keep just the job name
    raw_title = jd_parsed.get("job_title", "该岗位")
    title = raw_title.split("【")[0].split(" ")[0].strip() or "该岗位"

    result = []
    if responsibilities:
        for i, resp in enumerate(responsibilities[:2]):
            resp_short = resp[:80]
            result.append(InterviewQuestionItem(
                question_type="scenario",
                difficulty="hard",
                question=f"假设你入职 {title}，接到需求：{resp_short}。你会如何规划和实施？",
                why_ask="考察实际工作场景下的技术方案设计和项目规划能力",
                reference_answer="应涵盖: 需求分析 → 技术方案 → 实施步骤 → 风险评估",
                related_jd_requirement=f"岗位职责: {resp_short}",
            ))
    if len(result) < 2:
        result.append(InterviewQuestionItem(
            question_type="scenario",
            difficulty="hard",
            question=f"如果你加入 {title} 团队，发现现有系统性能瓶颈在数据库查询，你会如何排查和优化？",
            why_ask="考察系统性思维和性能优化能力",
            reference_answer="应涵盖: 问题定位(慢查询日志、EXPLAIN) → 优化方案(索引、缓存、SQL优化) → 验证效果",
        ))
    if len(result) < 2:
        result.append(InterviewQuestionItem(
            question_type="scenario",
            difficulty="hard",
            question=f"如果产品经理给你一个需求，你认为技术上不可行，你会如何处理？",
            why_ask="考察技术沟通和推动能力",
            reference_answer="应涵盖: 理解需求本质 → 提供替代方案 → 数据支撑 → 达成共识",
        ))
    return result


def _generate_behavioral() -> list[InterviewQuestionItem]:
    """Generate behavioral interview questions."""
    questions_pool = [
        ("请描述一次你在团队中遇到技术分歧的经历，你是如何处理的？", "考察团队协作和沟通能力"),
        ("你如何平衡代码质量和开发速度？能举个例子吗？", "考察工程素养"),
        ("请描述一次你在 deadline 压力下完成任务的经历", "考察抗压能力和时间管理"),
        ("你最近学了什么新技术？是怎么学的？", "考察学习能力和技术热情"),
    ]

    q = random.choice(questions_pool)
    return [InterviewQuestionItem(
        question_type="behavioral",
        difficulty="medium",
        question=q[0],
        why_ask=q[1],
        reference_answer="用 STAR 法则回答: Situation → Task → Action → Result",
    )]
