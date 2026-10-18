# ResumeMatch-AI 项目技术总结

> 面向求职场景的多 Agent 简历-JD 智能匹配分析系统 — 面试准备与简历包装文档

---

## 一、项目概述

### 1.1 项目简介

ResumeMatch-AI 是一个面向求职者的 AI 驱动简历-JD 智能匹配分析系统。系统解决的核心问题是：求职者投递简历时，无法量化评估自己与目标岗位的匹配程度，也无法获得针对性的简历优化建议。传统工具仅做关键词匹配，无法识别技能别名（如 py→Python）、无法验证技能是否在项目中实际使用、无法检查学历/经验等硬性要求。

系统实现了从 PDF 简历上传到可解释分析报告的端到端流程，核心能力包括：四维度加权评分、10 条规则诊断引擎、证据约束的 AI 简历改写、AI 模拟面试、以及多平台岗位搜索导入。

### 1.2 核心功能

| 功能模块 | 说明 | 技术实现 |
|---------|------|---------|
| 简历解析 | PDF 文本提取 → 结构化字段抽取（教育、技能、项目、经历） | PyMuPDF + 正则/LLM 双模式解析 |
| JD 解析 | 岗位描述 → 必备技能、加分项、职责、硬性要求 | 正则关键词匹配 + LLM 结构化抽取 |
| 四维度评分 | 技能匹配 40% + 项目相关性 25% + 语义相似度 20% + 硬性要求 15% | 规则引擎 + sentence-transformers Embedding |
| 简历诊断 | 10 条规则检测：缺失技能、弱描述、缺量化、模糊动词等 | 纯规则引擎，输出证据+建议+改写示例 |
| 技能归一化 | 200+ 别名字典，覆盖 8 个技术类别 | 三级匹配：精确→子串→未匹配兜底 |
| AI 简历改写 | 项目级改写 + 整份简历改写，证据链防编造 | DeepSeek LLM + 证据约束机制 + 质量门禁 |
| AI 模拟面试 | 面试题生成 + AI 对话面试 + 答案评分 | DeepSeek LLM + 规则兜底 |
| 岗位搜索 | BOSS 直聘、智联招聘、猎聘、前程无忧一键搜索 | Playwright 浏览器自动化 + API 拦截 |
| 报告导出 | Word / PDF 完整分析报告 | python-docx + ReportLab |

### 1.3 技术栈

```
前端: React 18 + TypeScript + Vite + Tailwind CSS + Recharts
后端: Python 3.9+ + FastAPI + SQLAlchemy 2.0 + Pydantic v2
数据库: MySQL 8.0+ (PyMySQL)
PDF 解析: PyMuPDF (fitz)
Embedding: sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) + TF-IDF 降级
LLM: DeepSeek / OpenAI 兼容接口，可选规则模式兜底
浏览器爬虫: Playwright + Edge (CDP)
报告生成: python-docx (Word) + ReportLab (PDF)
```

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React SPA)                        │
│  React 18 + TypeScript + Vite + Tailwind CSS + Recharts     │
│  7 个页面: 上传/JD/搜索/分析/报告/改写/面试                    │
└───────────────────────┬─────────────────────────────────────┘
                        │ REST API + JSON
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端 (FastAPI)                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              API Router 层 (4 个路由模块)              │   │
│  │  resume.py | job_description.py | analysis.py |      │   │
│  │  interview.py                                        │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Service 层 (18 个业务服务)                │   │
│  │                                                      │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │  │ 解析 Agent   │  │  评分 Agent   │  │ 诊断 Agent │  │   │
│  │  │ ResumeParse │  │  Scoring     │  │ Diagnosis  │  │   │
│  │  │ JDParse     │  │  (纯规则)     │  │ (纯规则)    │  │   │
│  │  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘  │   │
│  │         │                │                 │         │   │
│  │  ┌──────┴──────┐  ┌─────┴───────┐  ┌─────┴──────┐  │   │
│  │  │ 改写 Agent   │  │ 面试 Agent   │  │ 报告 Agent │  │   │
│  │  │ Rewrite     │  │ Interview   │  │ Report     │  │   │
│  │  │ (LLM+规则)  │  │ (LLM+规则)  │  │ (导出)     │  │   │
│  │  └─────────────┘  └─────────────┘  └────────────┘  │   │
│  │                                                      │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │ 基础设施: LLM Client | Embedding Service    │    │   │
│  │  │ Skill Normalizer | Playwright Browser Worker│    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────┴───────────────────────────────┐   │
│  │              数据层                                    │   │
│  │  MySQL 8.0 (7 张表) | 文件存储 (PDF/报告)              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心请求流程

**分析流程（核心链路）：**

```
用户上传 PDF → POST /resumes/upload → PyMuPDF 提取文本 → 存入 resumes 表
        ↓
用户输入 JD → POST /jds/ → 存入 job_descriptions 表
        ↓
点击"解析简历" → POST /resumes/{id}/parse
  → ResumeParseAgent: LLM/正则 双模式 → 结构化 JSON → 存入 parsed_json
        ↓
点击"解析 JD" → POST /jds/{id}/parse
  → JDParseAgent: LLM/正则 双模式 → 结构化 JSON → 存入 parsed_json
        ↓
点击"运行分析" → POST /analysis/run → AnalysisAgent 编排:
  ① ScoringAgent.compute_scores() → 四维度分数 + 匹配/缺失技能
  ② DiagnosisAgent.diagnose()     → 10 条诊断问题列表
  ③ _generate_ai_analysis()       → DeepSeek 深度分析（失败降级规则）
  ④ 持久化 → analysis_tasks + match_reports 表
        ↓
查看报告 → GET /analysis/{task_id}/report → 完整报告
简历改写 → POST /analysis/{task_id}/full-rewrite → 证据约束改写
面试准备 → POST /interview/start → AI 模拟面试
导出报告 → GET /analysis/{task_id}/export/word|pdf
```

### 2.3 Agent 协作流水线

```
                    ┌──────────────┐
                    │ ResumeParse  │ PDF → ParsedResume (Pydantic)
                    │ Agent        │ LLM 优先 → 正则 fallback
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │ JDParse      │ JD文本 → ParsedJD (Pydantic)
                    │ Agent        │ LLM 优先 → 正则 fallback
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
     ┌────────────────┐        ┌────────────────┐
     │ Scoring Agent  │        │ Diagnosis Agent│
     │ (纯规则引擎)    │        │ (10条规则)     │
     │ 四维度加权评分   │───┐    │ 问题+证据+建议 │
     └────────────────┘   │    └────────┬───────┘
                           │             │
                           ▼             ▼
                    ┌──────────────────────┐
                    │ AI Analysis Agent    │
                    │ DeepSeek 深度分析     │
                    │ → 优势/差距/行动计划  │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │ Rewrite Agent│ │Interview Agent│ │ Report Agent │
     │ 证据约束改写  │ │ AI模拟面试    │ │ Word/PDF导出 │
     │ 质量门禁检查  │ │ 答案评分      │ │ CJK字体处理  │
     └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 三、核心模块详解

### 3.1 四维度评分引擎 (Scoring Agent)

#### 核心设计思想

在设计评分系统前，需要解决一个核心问题：如何量化一份简历与一个岗位的匹配程度？市面上的工具大多使用单一的 cosine similarity，但它有两个致命缺陷：第一，分不清"我掌握 Python"和"JD 要求 Python"——两者在文本空间中几乎相同，但语义完全不同；第二，无法验证技能是否在项目中实际使用——简历列了一堆技术栈但项目描述里一个都没用到，cosine similarity 看不出来。

因此，我设计了四维度加权评分模型，每个维度解决一个特定问题：

**第一，技能匹配维度（40%）**。这个维度回答"你会不会我们要求的技术"。采用归一化集合对比：先把简历和 JD 的技能都做归一化（py→Python，k8s→Kubernetes），然后算必需技能命中率 × 90 + 加分技能 bonus × 10。为什么是 90+10？因为必需技能是不可妥协的，一个候选人有所有加分技能但没有必需技能不应该得高分。

**第二，项目相关性维度（25%）**。这个维度回答"你用这些技术做过什么"。每个项目从四个子维度打分：技术栈与 JD 重叠度（最高 40 分）、动作关键词命中（最高 30 分，如"开发""设计""优化"）、是否有量化指标（+20 分）、描述长度是否充分（+10 分）。没有量化指标的项目上限 60 分——用分数倒逼简历质量。

**第三，语义相似度维度（20%）**。这个维度回答"你的经历和这个岗位总体相不相关"。使用 sentence-transformers 多语言模型计算 embedding 余弦相似度，并做非线性校准（原始 cosine 0.01~0.05 映射到 35~95 分区间），同时混合主题关键词交集分。为什么只占 20%？因为语义相似度是"辅助信号"——一份写得很好但完全不相关的简历也能得到高 cosine，不能给太高权重。

**第四，硬性要求维度（15%）**。这个维度回答"你是否满足岗位的门槛条件"。检查学历层级（博士>硕士>本科>大专）和工作年限。满足得 100 分，未知得 60 分，不满足得 30 分。为什么只占 15%？因为系统不替 HR 做过滤决策——学历不满足但技能高度匹配的情况，应该由求职者自己判断是否投递。

#### 技术实现

```python
# scoring_service.py 核心评分逻辑

# 权重定义
W_SKILL = 0.40
W_PROJECT = 0.25
W_SEMANTIC = 0.20
W_REQUIREMENT = 0.15

def compute_scores(resume_parsed, jd_parsed, resume_raw_text, jd_raw_text):
    skill_score, skill_reason, matched, missing = _score_skills(resume_parsed, jd_parsed)
    project_score, project_reason = _score_projects(resume_parsed, jd_parsed)
    semantic_score, semantic_reason = _score_semantic(resume_raw_text, jd_raw_text)
    requirement_score, requirement_reason = _score_requirements(resume_parsed, jd_parsed)

    total = (skill_score * W_SKILL + project_score * W_PROJECT
             + semantic_score * W_SEMANTIC + requirement_score * W_REQUIREMENT)
    return ScoringResult(total_score=total, ...)
```

#### 技能归一化引擎

技能归一化是评分准确率的基础设施。采用**工厂注册模式**：通过 `_reg()` 函数批量注册技能别名到 `_SKILL_MAP` 字典，每条记录包含 canonical name、category 和 confidence。

```python
# skill_normalizer.py - 三级匹配策略

_SKILL_MAP: dict[str, tuple[str, str, float]] = {}

def _reg(canonical, category, confidence, *aliases):
    for alias in aliases:
        _SKILL_MAP[alias.lower()] = (canonical, category, confidence)
    _SKILL_MAP[canonical.lower()] = (canonical, category, confidence)

# 注册示例
_reg("Python", CAT_PROGRAMMING, 0.99, "python", "py", "python3", "python2")
_reg("Kubernetes", CAT_DEVOPS, 0.99, "kubernetes", "k8s", "kube")

def normalize_skill(skill: str) -> NormalizedSkill:
    key = skill.strip().lower()
    # Level 1: 精确匹配 (confidence 0.95-0.99)
    if key in _SKILL_MAP:
        return NormalizedSkill(...)
    # Level 2: 子串匹配 (confidence -0.1)
    for alias, (name, cat, conf) in _SKILL_MAP.items():
        if alias in key or key in alias:
            return NormalizedSkill(confidence=max(0.0, conf - 0.1), ...)
    # Level 3: 未匹配兜底 (confidence 0.3)
    return NormalizedSkill(name=skill.strip().title(), category="other", confidence=0.3)
```

200+ 条别名覆盖 8 个类别：

| 类别 | 示例 | 数量 |
|------|------|------|
| programming_language | Python, Java, Go, C++, Rust, TypeScript | ~30 |
| frontend | React, Vue, Angular, Next.js, Tailwind CSS | ~25 |
| backend | FastAPI, Django, Flask, Spring Boot, Express | ~25 |
| database | MySQL, PostgreSQL, MongoDB, Redis, Elasticsearch | ~20 |
| ai_ml | PyTorch, TensorFlow, LangChain, RAG, Transformer | ~35 |
| devops | Docker, Kubernetes, AWS, GCP, Terraform, CI/CD | ~30 |
| tool | Git, Kafka, RabbitMQ, Nginx, Postman | ~25 |
| soft_skill | 沟通能力, 团队协作, 项目管理 | ~15 |

#### 语义相似度校准

原始 cosine similarity 对中文 JD/简历的值通常在 0.01~0.05，直接显示为 1~5 分会产生误导。采用非线性校准：

```python
def _score_semantic(resume_text, jd_text):
    raw_similarity = service.compute_similarity(resume_text, jd_text)  # 0.0~1.0
    # 非线性校准：35 + 60 * sqrt(raw_similarity)
    vector_score = 35.0 + 60.0 * math.sqrt(raw_similarity)
    # 混合主题关键词交集分
    keyword_score = 35.0 + 60.0 * math.sqrt(min(len(overlap), denominator) / denominator)
    score = vector_score * 0.62 + keyword_score * 0.38
    return max(35.0, min(95.0, score))
```

#### 边界情况处理

| 场景 | 处理方式 |
|------|---------|
| JD 无技能要求 | req_ratio 默认 0.8，skill_score = 72 |
| JD 无硬性要求 | requirement_score = 70（中性分） |
| 简历无项目经历 | project_score = 30（惩罚分） |
| 项目无量化指标 | project_score 上限 60 |
| Embedding 模型未缓存 | 自动降级到 TF-IDF |
| 技能归一化未命中 | 保留原词，标记 confidence=0.3 |

### 3.2 诊断引擎 (Diagnosis Agent)

#### 核心设计思想

评分回答"多匹配"，诊断回答"为什么不够匹配 + 怎么改"。两者独立运行但数据共享——ScoringAgent 输出的 matched_skills 和 missing_skills 直接传给 DiagnosisAgent。

诊断引擎采用**规则链模式**：10 个独立检查函数顺序执行，每个函数返回 `DiagnosisIssue[]` 或空列表。所有函数的输出聚合为最终诊断结果。

#### 10 条诊断规则

| # | 规则类型 | 严重程度 | 检查内容 |
|---|---------|---------|---------|
| 1 | missing_required_skill | high | JD 必备技能在简历中缺失 |
| 2 | weak_project_description | high/medium | 项目描述为空/过短(<20字)/过于笼统 |
| 3 | lack_of_metrics | medium | 项目缺少量化指标（百分比、数据量、响应时间等） |
| 4 | skill_not_reflected_in_project | medium | 技能栏列出但项目中未体现 |
| 5 | irrelevant_project | low | 项目技术栈与 JD 无交集 |
| 6 | unclear_role | medium | 项目角色未说明或模糊（"参与""负责"） |
| 7 | vague_action | medium | 使用模糊动词（参与、负责、了解、熟悉、学习、协助） |
| 8 | missing_business_context | low | 项目缺少业务场景/背景描述 |
| 9 | missing_technical_detail | medium | 项目缺少技术实现细节 |
| 10 | format_issue | medium/high | 缺少姓名、联系方式、技能清单 |

每条诊断输出包含完整结构：

```python
DiagnosisIssue(
    type="missing_required_skill",       # 机器可读分类
    severity="high",                     # high/medium/low
    title="缺少必备技能: Docker",          # 人类可读标题
    evidence="JD 要求具备 [Docker] 技能", # 原文证据
    reason="该技能是岗位核心要求",          # 原因分析
    suggestion="在技能栏补充 Docker",     # 可执行建议
    rewrite_example="技能栏添加: Docker"   # 改写示例
)
```

#### 设计模式

- **规则链模式 (Chain of Responsibility)**：10 个检查函数顺序执行，每个独立、可单独测试
- **策略模式**：每条规则是一个策略，可以独立增删改而不影响其他规则

### 3.3 LLM 集成与降级策略

#### 核心设计思想

系统需要在"AI 智能"和"系统可靠性"之间取得平衡。LLM 调用可能失败（网络超时、API Key 无效、返回格式异常），但系统不能因此不可用。因此采用**三层防护 + 自动降级**架构。

#### 三层防护

```
Layer 1: 文本预处理
  - 提取 ```json``` 代码块
  - 清理 trailing comma
  - 去除 Markdown 标记

Layer 2: JSON 解析
  - json.loads 解析
  - 正则提取 { } 或 [ ] 包裹的内容

Layer 3: Pydantic 校验
  - 严格类型检查
  - 字段缺失自动填充默认值
  - 校验失败抛出 LLMCallError
```

#### 自动降级策略

| Agent | LLM 可用时 | LLM 不可用时 |
|-------|-----------|-------------|
| ResumeParse | LLM 结构化抽取 | 正则表达式提取 |
| JDParse | LLM 结构化抽取 | 关键词匹配提取 |
| Scoring | 纯规则（不依赖 LLM） | 纯规则 |
| Diagnosis | 纯规则（不依赖 LLM） | 纯规则 |
| AI Analysis | DeepSeek 深度分析 | 规则生成基础分析 |
| Full Rewrite | LLM 证据约束改写 | 模板化规则改写 |
| Interview | LLM 对话面试 | 预置题库 + 规则评分 |

```python
# llm_client.py - 工厂模式创建 LLM 客户端

def get_llm_client() -> BaseLLMClient:
    provider = settings.LLM_PROVIDER  # mock / openai / deepseek
    if provider in {"", "mock", "rule"}:
        return MockLLMClient()         # 规则兜底
    elif provider in {"openai", "deepseek"}:
        return OpenAICompatibleLLMClient()  # OpenAI 兼容接口
```

#### 设计模式

- **工厂模式**：`get_llm_client()` 根据配置创建不同的 LLM 客户端
- **策略模式**：`BaseLLMClient` 定义统一接口，`MockLLMClient` 和 `OpenAICompatibleLLMClient` 是不同策略
- **单例模式**：`_client_instance` 全局缓存，避免重复创建

### 3.4 证据约束改写 (Rewrite Agent)

#### 核心设计思想

这是项目最大的差异化功能。市面上的 AI 简历工具最大的问题是 LLM 会编造经历——把你没做过的项目写成做过的，编造不存在的指标。我的解决方案是**证据链机制**。

每条改写输出不只是一个文本，而是拆分为：
- `resume_evidence`：从原简历中溯源——证明候选人真的做过
- `jd_evidence`：从 JD 中匹配——说明岗位需要什么

**风险判定矩阵**：
- 有简历事实证据 + 有 JD 需求证据 → low risk（改写可信）
- 有简历事实证据 + 无 JD 需求证据 → low risk（改写可信但可能不相关）
- 无简历事实证据 + 有 JD 需求证据 → high risk（可能是编造！前端橙标提示）
- 无简历事实证据 + 无 JD 需求证据 → high risk（不输出）

#### 质量门禁 (5 项检查)

```python
# resume_rewrite_quality.py - 确定性后处理

def post_process_rewritten_resume(data, ...):
    # 1. 直接投递格式检查
    # 2. 技术栈清洗（去除 GitHub/URL/过细依赖）
    # 3. 语气检查（实习生不应出现"精通""架构师"）
    # 4. 量化数据真实性检查（只保留原简历已有数字）
    # 5. 证据链风险重评
```

#### 技术栈清洗规则

自动将过细的依赖名映射为能力描述：

| 原始依赖 | 清洗结果 |
|---------|---------|
| PyMuPDF | PDF 文本解析 |
| pdf-parse | PDF 解析 |
| bcryptjs | 密码加密 / Cookie Session |
| ReportLab | PDF 报告导出 |
| Recharts | 数据可视化 |

#### 设计模式

- **模板方法模式**：改写流程固定（加载数据→LLM 改写→质量门禁→持久化），具体步骤可替换
- **策略模式**：LLM 改写和规则改写是两种策略，通过配置切换
- **装饰器模式**：质量门禁在改写输出上做后处理，不修改改写逻辑本身

### 3.5 招聘平台爬虫 (Platform Crawler)

#### 核心设计思想

爬虫需要解决的核心问题：不同招聘平台的数据结构、API 格式、反爬策略完全不同，但下游分析代码需要统一的数据格式。因此采用**适配器模式**：每个平台有独立的爬取逻辑，但输出统一的 `JobCard` 数据结构。

#### 多平台适配架构

```
PlatformCrawlerService
  ├── BOSS 直聘: API 拦截 + DOM 提取双通道
  ├── 智联招聘: API 拦截 + DOM 提取双通道
  ├── 猎聘: API 拦截 (jobCardList 嵌套结构)
  └── 前程无忧: API 拦截 (jobListItemVO 嵌套提升)

每个平台:
  ① 打开搜索页 → Playwright 监听 JSON 响应
  ② 解析 API 返回的岗位列表
  ③ 降级到 DOM 卡片提取（API 失败时）
  ④ 统一归一化为 JobCard 格式
  ⑤ 城市过滤 + 去重 + 匹配评分
```

#### 关键技术实现

- **CDP 进程管理**：通过 Edge 远程调试端口连接已有浏览器实例，复用用户登录态
- **双通道提取**：API 拦截（高效）+ DOM 提取（兜底），确保数据完整性
- **搜索缓存**：`cached_job_searches` 表以 (keyword, city, platforms, pages, job_type, experience, education) 为联合缓存 key，缓存命中时对当前简历重新评分后返回，耗时 < 1 秒（vs. 重新爬取 1-6 分钟）
- **城市过滤**：50+ 城市字典 + 通用正则匹配（`XX市`、`XX·YY` 模式）

#### 设计模式

- **适配器模式**：每个平台一个适配器，统一输出 `JobCard` 格式
- **策略模式**：平台选择是策略切换
- **缓存模式**：搜索结果 DB 缓存，避免重复爬取

### 3.6 AI 模拟面试 (Interview Agent)

#### 核心设计思想

面试准备需要三个能力：生成针对性面试题、AI 对话式面试、答案评分。采用 LLM + 规则双模式：LLM 提供灵活的对话和评分，规则引擎保证系统在无 API Key 时仍可使用。

#### 面试题生成

```
输入: resume_parsed + jd_parsed + matched/missing_skills
  ↓
生成 10 道题:
  ├── 3 道技术题: 从 JD 必备技能中提取，匹配预置模板
  ├── 3 道项目题: 深挖简历项目经历
  ├── 2 道缺口题: 针对缺失技能，考察学习能力
  ├── 1 道场景题: 基于 JD 职责设计
  └── 1 道行为题: 从题库随机抽取
```

#### 模拟面试对话

```
start_interview() → 加载上下文 → LLM 生成开场问题（降级: 预置题库）
  ↓
interview_chat(message, history) → LLM 追问对话（降级: 规则回复）
  ↓
finish_interview(history) → LLM 综合评分（降级: 规则评分）
```

#### 设计模式

- **状态模式**：面试有明确的状态流转（未开始→进行中→已结束）
- **策略模式**：LLM 对话和规则对话是两种策略

---

## 四、数据库设计

### 4.1 ER 关系图

```
resumes (简历)                    job_descriptions (岗位 JD)
  ├── id (PK)                       ├── id (PK)
  ├── filename                      ├── title
  ├── raw_text                      ├── company
  ├── parsed_json (TEXT)            ├── raw_text
  └── created_at                    ├── parsed_json (TEXT)
                                    └── created_at
         │                               │
         └───────────┬───────────────────┘
                     ▼
           analysis_tasks (分析任务)
             ├── id (PK)
             ├── resume_id (FK → resumes)
             ├── jd_id (FK → job_descriptions)
             ├── status (pending/processing/completed/failed)
             ├── created_at
             └── updated_at
                     │
         ┌───────────┼───────────────┐
         ▼           ▼               ▼
  match_reports   rewritten_     interview_
  (匹配报告)      resumes        questions
  ├── id (PK)     (改写简历)     (面试题)
  ├── task_id FK  ├── id (PK)    ├── id (PK)
  ├── total_score ├── task_id FK ├── task_id FK
  ├── skill_score ├── rewritten_ ├── question
  ├── project_score│  text       ├── answer
  ├── semantic_score├── edited_  ├── score
  ├── requirement_ │  text       └── created_at
  │  score        ├── source
  ├── matched_    └── quality_gate_json
  │  skills_json
  ├── missing_skills_json
  ├── problems_json
  ├── suggestions_json
  └── report_json

cached_job_searches (搜索缓存)
  ├── id (PK)
  ├── keyword
  ├── city
  ├── platforms_json
  ├── pages, job_type, experience, education
  ├── total_found, total_after_filter
  ├── jobs_json (完整岗位列表)
  └── errors_json (平台异常信息)
```

### 4.2 设计决策

**关系 + JSON 混合存储**：结构化字段（ID、状态、分数、时间）走列，AI 解析结果（嵌套结构）以 JSON 字符串存入 TEXT 字段。

选择这个方案而非纯关系型或纯文档型的原因：
- 纯关系型（EAV 模式）：开发成本高，查询复杂
- 纯 MongoDB：无法高效 JOIN 和按分数排序
- 混合方案：需要查询排序的放结构列，不需要查询的嵌套数据放 JSON 列

### 4.3 索引策略

```sql
-- 外键索引（自动创建）
analysis_tasks.resume_id → INDEX
analysis_tasks.jd_id → INDEX

-- 唯一索引
match_reports.task_id → UNIQUE INDEX

-- 联合缓存 key
cached_job_searches → (keyword, city, platforms_json, pages, job_type, experience, education)
```

---

## 五、前端架构

### 5.1 页面结构

```
frontend/src/
├── api/                    # 5 个 API 模块
│   ├── resume.ts          #   简历 API
│   ├── jobDescription.ts  #   JD API
│   ├── analysis.ts        #   分析 API
│   ├── interview.ts       #   面试 API
│   └── platform.ts        #   平台搜索 API
├── components/             # 14 个 UI 组件
│   ├── Layout.tsx         #   布局组件
│   ├── ScoreChart.tsx     #   分数图表
│   ├── DiagnosisCard.tsx  #   诊断卡片
│   └── ...
├── pages/                  # 7 个页面
│   ├── UploadPage.tsx     #   简历上传
│   ├── JDPage.tsx         #   JD 输入
│   ├── PlatformSearchPage.tsx # 平台搜索
│   ├── AnalysisPage.tsx   #   分析运行
│   ├── ReportPage.tsx     #   报告查看
│   ├── RewritePage.tsx    #   简历改写
│   └── InterviewPage.tsx  #   面试准备
└── types/                  # 4 个类型定义
    ├── resume.ts
    ├── jobDescription.ts
    ├── analysis.ts
    └── interview.ts
```

### 5.2 状态管理

使用 React 内置的 `useState` + `useEffect`，未引入 Redux。原因：状态主要在页面级别（上传的简历、分析结果），跨页面共享少（taskId 通过 URL params 传递）。

### 5.3 技术选型对比

| 方案 | 优点 | 缺点 | 选择理由 |
|------|------|------|---------|
| useState + useEffect | 零依赖、简单直接 | 复杂状态难管理 | 当前规模够用 |
| Redux | 全局状态管理、DevTools | 样板代码多、学习成本高 | 过度设计 |
| Zustand | 轻量、API 简洁 | 需额外依赖 | 未来可考虑 |

---

## 六、后端技术栈详解

### 6.1 FastAPI

**是什么**：FastAPI 是一个现代、高性能的 Python Web 框架，基于 Starlette 和 Pydantic，支持异步请求处理和自动生成 OpenAPI 文档。

**为什么选它**：
1. 原生 Pydantic 集成：请求体自动校验，不合法输入直接 422 拒绝
2. 异步支持：基于 asyncio，适合 I/O 密集型场景（LLM 调用、爬虫）
3. 自动 API 文档：`/docs` 端点自动生成 Swagger UI，前端开发效率高

**替代方案**：
- Django：全功能框架但太重，不需要 ORM/Admin/模板引擎
- Flask：轻量但缺乏原生类型校验和异步支持

### 6.2 SQLAlchemy 2.0

**是什么**：Python ORM 框架，2.0 版本引入了新的 Mapped 声明式语法。

**核心用法**：
```python
class AnalysisTask(BaseModel):
    __tablename__ = "analysis_tasks"
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending)
    resume = relationship("Resume", lazy="noload")
```

**为什么选它**：
1. 类型安全：Mapped 类型注解配合 IDE 自动补全
2. 关系定义清晰：relationship + ForeignKey 声明式定义
3. 社区成熟：Python 生态最主流的 ORM

### 6.3 Pydantic v2

**是什么**：Python 数据校验库，v2 版本使用 Rust 重写核心，性能提升 5-50 倍。

**核心用法**：
```python
class ScoreDetail(BaseModel):
    skill_score: float = 0.0
    skill_reason: str = ""
    project_score: float = 0.0
    # ...

# LLM 输出校验
data = client.chat_json(system_prompt, user_prompt)  # 返回 dict
score_detail = ScoreDetail(**data)  # 自动校验类型
```

**为什么选它**：
1. LLM 输出校验：LLM 返回的 JSON 格式不稳定，Pydantic 做严格类型检查
2. FastAPI 原生集成：请求/响应模型自动校验和文档生成
3. 性能：v2 比 v1 快 5-50 倍

### 6.4 sentence-transformers

**是什么**：基于 Transformer 的句子嵌入库，支持 100+ 预训练模型。

**为什么选它**：
1. 多语言支持：`paraphrase-multilingual-MiniLM-L12-v2` 支持中英文混合
2. 384 维向量：轻量但质量足够
3. 本地运行：无需外部 API，无网络延迟

**降级策略**：
```python
def get_embedding_service() -> BaseEmbeddingService:
    if _is_model_cached(settings.EMBEDDING_MODEL):
        return SentenceTransformerEmbeddingService()  # 高质量
    else:
        return TFIDFEmbeddingService()  # 轻量降级
```

### 6.5 Playwright

**是什么**：微软开发的浏览器自动化框架，支持 Chromium/Firefox/WebKit。

**为什么选它**：
1. CDP 协议支持：可以连接已运行的 Edge 浏览器实例，复用用户登录态
2. API 拦截能力：`page.on("response")` 可以监听网络请求，直接获取结构化数据
3. 异步原生：基于 asyncio，与 FastAPI 技术栈一致

**替代方案**：
- Selenium：API 拦截能力弱，不支持 CDP
- requests + BeautifulSoup：无法处理 SPA 页面和登录态

---

## 七、安全与认证

### 7.1 当前状态

目前系统没有用户认证，所有 API 端点公开访问。定位是个人工具/Demo 级别。

### 7.2 生产环境需要的安全措施

| 措施 | 说明 |
|------|------|
| JWT 认证 | 用户登录后签发 Token，API 请求携带 Authorization header |
| API 限流 | 对 LLM 调用和爬虫接口做限流，防止滥用 |
| CORS 配置 | 限制允许的源 |
| 输入校验 | Pydantic 已覆盖，但需要额外检查文件大小和类型 |
| LLM API Key 保护 | .env 文件不进版本控制，API Key 不暴露给前端 |

---

## 八、部署与运维

### 8.1 启动方式

```bash
# 后端 (端口 9000)
cd backend && python main.py

# 前端 (端口 5173)
cd frontend && npm run dev

# 爬虫 (独立进程)
python -m job_crawler
```

### 8.2 环境变量

```env
DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/resume_match?charset=utf8mb4
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
LLM_STRICT_MODE=true
EDGE_REMOTE_DEBUG_PORT=9333
```

### 8.3 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 9000 | 从 8000 改为 9000，避免 Windows Hyper-V 预留端口冲突 |
| 前端 Dev | 5173 | Vite 默认端口 |
| Edge CDP | 9333 | 浏览器远程调试端口 |

---

## 九、面试 Q&A

### 9.1 项目介绍类

**Q: 介绍一下这个项目**

A: 这是一个面向求职场景的多 Agent AI 系统，叫 ResumeMatch-AI。核心功能是把简历 PDF 和目标 JD 做四维匹配评分，然后做简历诊断和 AI 改写。最大的差异化是证据约束改写——防止 LLM 编造经历。技术栈是 FastAPI + React + MySQL，8 个 Agent 顺序协作，每个有独立的输入输出和回退策略。

**可能追问**：

- Q: 你说的 Agent 是怎么实现的？用 LangChain 了吗？
  A: 没用 LangChain。我的 Agent 就是普通的 Python service 类，放在 `backend/app/services/` 下面。每个 Agent 是一个模块，有独立的函数，接收 Pydantic schema 作为输入，返回 Pydantic schema 作为输出。内部有 LLM 调用逻辑和规则 fallback。Agent 间是函数调用，不是 HTTP 或消息队列。不用框架实现 Agent，体现对概念的理解而非框架熟练度——Agent 的本质是有输入输出、有决策逻辑、有工具调用的模块，不需要 LangChain 这样的框架来定义。

- Q: 为什么叫"多 Agent"而不是"多个服务"？
  A: 因为每个模块具备 Agent 的核心特征：**自主决策**（自己决定调 LLM 还是走规则）、**工具使用**（调用 LLM API、调用 Embedding 服务、操作数据库）、**目标驱动**（解析 Agent 的目标是输出结构化数据，评分 Agent 的目标是输出匹配分数）。这比普通的 CRUD 服务多了"决策"维度。

---

### 9.2 评分模型类

**Q: 你的评分模型是怎么设计的？为什么不用 cosine similarity？**

A: 两个原因。第一，cosine similarity 分不清"我掌握 Python"和"JD 要求 Python"——两者在文本空间中几乎相同，但语义完全不同。第二，它无法验证技能是否在项目中实际使用——简历列了一堆技术栈但项目描述里一个都没用到，cosine similarity 看不出来。

所以我设计了四维度加权评分：技能匹配 40%（归一化集合对比）、项目相关性 25%（技术栈重叠 + 动作关键词 + 量化指标）、语义相似度 20%（embedding cosine，做非线性校准）、硬性要求 15%（学历/年限校验）。每个维度解决一个特定问题，每个分数都有可追溯的原因字符串。

**可能追问**：

- Q: 为什么权重是 40/25/20/15？怎么确定的？
  A: 技能是面试邀请的最强信号——HR 筛简历第一眼看技能匹配，所以占 40%。项目是技能落地的证据——光列技能没有用，要在项目中体现，占 25%。语义是辅助信号——一份写得好但不相关的简历也能得高 cosine，所以只给 20%。硬性要求是门槛——太低不起作用（15% 已经足够拉低不匹配的简历），太高会让软性匹配失去意义。

- Q: 技能归一化具体怎么做？
  A: 三级匹配策略。第一级精确匹配：`"py".lower()` 在 `_SKILL_MAP` 字典中直接命中，返回 canonical name "Python"，confidence 0.99。第二级子串匹配：输入是 `"python3.11"`，虽然字典里没有这个精确 key，但 `"python"` 是它的子串，返回 "Python"，confidence 降低 0.1。第三级未匹配兜底：返回 title-cased 原始字符串，category="other"，confidence 0.3。200+ 条别名通过 `_reg()` 函数批量注册，覆盖 8 个技术类别。

- Q: 无量化指标上限 60 分，会不会太严格？
  A: 这是刻意设计。项目描述没有量化数据（"负责后端开发"vs"开发了 15 个 API，支撑日均 5 万次调用"）确实缺乏说服力。60 分上限用分数倒逼简历质量。但我也考虑了岗位差异——对于确实不好量化的岗位（如设计），诊断给出的是 suggestion 而非强制扣分。

- Q: 语义分为什么要做非线性校准？
  A: 因为原始 cosine similarity 对中文文本的值通常在 0.01~0.05，直接乘以 100 显示为 1~5 分会产生误导——用户看到 5 分会觉得"完全不相关"，但实际上中文 JD 和简历的 cosine 本来就低。校准公式 `35 + 60 * sqrt(cosine)` 把 0.01 映射到 41 分、0.05 映射到 48 分，更符合直觉。

---

### 9.3 诊断引擎类

**Q: 你的诊断引擎怎么工作的？**

A: 10 条纯规则，逐项检查简历。每条规则是一个独立函数，接收简历和 JD 的结构化数据，返回 DiagnosisIssue 列表或空列表。10 条规则覆盖：缺失必需技能、项目描述过短、缺少量化指标、技能声明未在项目中体现、项目与 JD 无交集、角色不明确、使用模糊动词、缺少业务场景、缺少技术细节、格式问题。每条输出包含：问题类型、严重程度、原文证据、原因分析、改进建议和改写示例。

**可能追问**：

- Q: 诊断和评分是什么关系？
  A: 评分回答"多匹配"（一个数字），诊断回答"为什么不够匹配 + 怎么改"（结构化建议）。两者独立运行但数据共享——ScoringAgent 输出的 matched_skills 和 missing_skills 直接传给 DiagnosisAgent。评分不影响诊断结果，诊断不影响评分结果。

- Q: 10 条规则怎么保证覆盖全面？
  A: 从简历的结构维度拆解：基本信息（格式问题）→ 技能栏（缺失技能、技能未体现）→ 项目经历（描述质量、量化指标、角色明确性、技术细节、业务背景）→ 整体（与 JD 的相关性）。每个维度至少有一条规则覆盖。

---

### 9.4 LLM 集成类

**Q: 你如何防止 LLM 输出不稳定？**

A: 三层防护。第一层文本预处理：提取 ```json``` 代码块、清理 trailing comma、去除 Markdown 标记。第二层 JSON 解析：json.loads 解析，失败则用正则提取 `{ }` 或 `[ ]` 包裹的内容。第三层 Pydantic 校验：严格类型检查，字段缺失自动填充默认值。任何一层失败都降级到规则引擎。

**可能追问**：

- Q: LLM 调用失败了怎么办？
  A: 所有调 LLM 的 Agent 都有规则兜底。ResumeParseAgent → regex 提取。JDParseAgent → 关键词匹配。FullRewriteAgent → 模板化改写。InterviewAgent → 预置题库。评分和诊断本身就是规则引擎，不依赖 LLM。系统在任何环境下都不会白屏。LLM 失败对用户体验的影响是"改写建议没那么智能"，而不是"系统不可用"。

- Q: prompt 模板怎么管理的？
  A: 8 个 prompt 模板独立成 .md 文件，放在 `backend/app/prompts/` 目录下。通过 `prompt_render.py` 工具加载和渲染。这样做的好处：prompt 和代码解耦，改 prompt 不用改 Python 代码；prompt 可以单独版本管理和 review；方便做 A/B 测试。

- Q: temperature 参数怎么设置的？
  A: 分析和改写用 0.15（低温度，保证输出稳定），面试对话用 0.7（较高温度，保证对话自然）。评分和诊断不调 LLM，完全确定性。

---

### 9.5 证据约束改写类

**Q: 你如何防止 LLM 在改写简历时编造经历？**

A: 这是我自己发现的问题——市面上的 AI 简历工具经常编造经历。我的解决方案是证据约束机制。改写输出不只是一个文本，每条关键描述都有证据链：resume_evidence 从原简历中溯源（证明我真的做过），jd_evidence 从 JD 中匹配（说明岗位需要什么）。然后通过风险判定矩阵做分类——只有 JD 需求但没简历事实支撑的改写标为 high risk，前端橙标提示需要人工确认。

**可能追问**：

- Q: 风险判定矩阵具体怎么实现的？
  A: 四种组合：有简历证据 + 有 JD 证据 → low risk（改写可信）。有简历证据 + 无 JD 证据 → low risk（可信但可能不相关）。无简历证据 + 有 JD 证据 → high risk（可能是编造！因为 JD 说需要这个技能但原简历没有，改写里出现了就需要警惕）。无简历证据 + 无 JD 证据 → high risk（不输出）。

- Q: 质量门禁有哪几项检查？
  A: 5 项确定性检查：直接投递格式检查（确保改写结果可以直接用）、技术栈清洗（去除 GitHub/URL/过细依赖，映射为能力描述）、语气检查（实习生不应出现"精通""架构师"等夸大词）、量化数据真实性检查（只保留原简历已有数字，新增指标标记 warning）、证据链风险重评。

---

### 9.6 爬虫类

**Q: 你的爬虫怎么实现的？怎么处理不同平台的差异？**

A: 采用适配器模式。每个招聘平台（BOSS 直聘、智联招聘、猎聘、前程无忧）有独立的爬取逻辑，但输出统一的 JobCard 数据结构。爬取策略是双通道：优先 API 拦截（监听 Playwright 的 network response，直接获取结构化 JSON），失败降级到 DOM 卡片提取。通过 Edge 远程调试端口连接已有浏览器实例，复用用户登录态。

**可能追问**：

- Q: 为什么不直接用 requests？
  A: 三个原因。第一，这些平台都是 SPA（单页应用），HTML 里没有数据，数据通过 JS 动态加载。第二，需要登录态，Playwright 可以复用用户已登录的浏览器。第三，需要 API 拦截能力——直接监听浏览器的网络请求比模拟请求更稳定。

- Q: 搜索缓存怎么设计的？
  A: 新增 `cached_job_searches` 数据库表，以 (keyword, city, platforms, pages, job_type, experience, education) 为联合缓存 key。缓存存储完整去重岗位列表（all_jobs JSON），不受 min_score/top 过滤影响——用户调整筛选条件后仍可命中缓存。缓存不限时保留，只有手动清空才清除。缓存命中时对当前简历重新评分后返回，耗时 < 1 秒（vs. 重新爬取 1-6 分钟）。

- Q: 城市过滤怎么做的？
  A: 50+ 城市字典 + 通用正则匹配。先用已知城市列表匹配，再用通用正则提取（`XX市` 模式、`XX·YY` 模式）。能明确识别为其他城市时直接拒绝。修复了"城市字段被篡改"的 bug——之前把外地岗位的城市字段改成了目标城市，现在改为硬过滤。

---

### 9.7 数据库设计类

**Q: 为什么用 JSON 列存解析结果？**

A: 工程权衡。简历的解析结果是嵌套结构——项目里有 tech_stack 数组，教育经历是对象数组。用传统关系型需要 EAV 模式或多表 JOIN，开发成本高。用纯 MongoDB 就没法高效 JOIN 和按分数排序。MySQL 8.0 的 JSON 支持让我可以：需要查询排序的（ID、状态、分数、时间）放结构列，不需要查询的嵌套数据放 JSON 列。兼顾了查询性能和 schema 灵活性。

**可能追问**：

- Q: JSON 列有什么缺点？
  A: 最大的缺点是无法高效查询 JSON 内部字段——比如"找所有掌握 Python 的简历"需要全表扫描 + JSON 解析。解决方案：如果这类查询成为高频需求，可以把关键字段提取到独立列，或者引入 Elasticsearch 做全文索引。

- Q: 为什么不用 MongoDB？
  A: 因为需要关系查询——analysis_tasks 需要 JOIN resumes 和 job_descriptions，match_reports 需要按 task_id 关联。MongoDB 的 $lookup 效率不如 SQL JOIN。而且 Pydantic + SQLAlchemy 的类型安全开发体验比 pymongo 好很多。

---

### 9.8 前端类

**Q: 前端状态管理怎么做的？**

A: 用的是 React 内置的 useState + useEffect，没有引入 Redux。原因：状态主要在页面级别（上传的简历、分析结果），跨页面共享少（taskId 通过 URL params 传递）。对于当前规模够了。如果以后要做全局用户状态、多简历管理等复杂状态，会考虑 Zustand。

**可能追问**：

- Q: 前端怎么和后端通信？
  A: REST JSON over HTTP。前端 axios 封装 API 调用，FastAPI router 接收请求，Pydantic 做类型校验。不合法的请求体会被 FastAPI 直接 422 拒绝。前端 Vite 配置了代理，开发环境的 `/api` 请求代理到 `http://localhost:9000`。

---

### 9.9 设计模式类

**Q: 你用了什么设计模式？**

A: 主要用了五种设计模式：

1. **策略模式**：LLM 客户端（Mock/OpenAI/DeepSeek）、Embedding 服务（TF-IDF/SentenceTransformer）、改写策略（LLM/规则）都是策略模式——同一接口，不同实现，通过配置切换。

2. **工厂模式**：`get_llm_client()` 和 `get_embedding_service()` 根据配置创建不同实例。

3. **单例模式**：LLM 客户端和 Embedding 服务全局缓存一个实例，避免重复创建。

4. **适配器模式**：四个招聘平台有独立爬取逻辑，但输出统一的 JobCard 格式。

5. **规则链模式 (Chain of Responsibility)**：诊断引擎的 10 条规则顺序执行，每条独立可测试。

**可能追问**：

- Q: 策略模式和状态模式的区别？
  A: 策略模式是"同一行为的不同实现"——比如评分可以用规则或 LLM，是策略切换。状态模式是"对象在不同状态下行为不同"——比如分析任务在 pending/processing/completed/failed 状态下的行为不同。策略模式的策略是外部注入的，状态模式的状态是对象内部管理的。

- Q: 工厂模式的 Map 怎么初始化的？
  A: `get_llm_client()` 不是用 Map 初始化的，而是用 if-elif 分支：`provider == "deepseek"` → 创建 `OpenAICompatibleLLMClient`，`provider in {"mock", "rule"}` → 创建 `MockLLMClient`。技能归一化的 `_SKILL_MAP` 才是 Map 初始化——通过 `_reg()` 函数在模块加载时批量注册。

---

### 9.10 性能优化类

**Q: 有什么性能优化？**

A: 几个关键优化：
1. 搜索缓存：DB 缓存搜索结果，命中时 < 1 秒返回（vs. 重新爬取 1-6 分钟）
2. Embedding 模型缓存：检查本地 HuggingFace 缓存目录，模型已下载则直接加载，未下载则降级 TF-IDF
3. LLM 客户端单例：全局缓存一个实例，避免每次请求重新创建
4. 前端 localStorage 持久化：搜索条件和结果存入 localStorage，页面恢复时零网络请求

**可能追问**：

- Q: 分析流程是同步的还是异步的？
  A: 目前是同步的——整个分析流程在一个 HTTP 请求中完成。大 PDF 或慢 Embedding 模型可能导致超时。这是当前的一个局限，未来计划用 Celery + Redis 做异步任务队列。

- Q: 如果用户量增长，有什么瓶颈？
  A: 主要瓶颈在 LLM 调用——每次分析至少调用 1-3 次 LLM（解析 + 深度分析 + 改写），每次调用 2-10 秒。解决方案：异步任务队列 + LLM 调用并发控制 + 结果缓存。数据库层面，JSON 列的查询效率是另一个瓶颈，可以引入 Elasticsearch。

---

### 9.11 工程实践类

**Q: 你遇到过什么技术难点或 bug？**

A: 三个典型的：

1. **LLM 输出 JSON 格式不稳定**：DeepSeek 有时返回带 trailing comma 的 JSON，有时用 Markdown 代码块包裹。解决方案：三层防护——文本预处理 → json.loads → Pydantic 校验，任何一层失败都降级到规则引擎。

2. **PDF 中文导出显示问号**：ReportLab 默认不支持 CJK 字体，导出的中文全部显示为 `?`。解决方案：手动注册 CJK 字体（`registerPdfFont`）+ 清洗 emoji 和特殊符号。

3. **猎聘/前程无忧 0 岗位**：API 返回的数据结构和预期不同——猎聘的岗位在 `data.data.jobCardList` 嵌套路径下，前程无忧的字段嵌套在 `jobListItemVO` 子对象中。解决方案：新增容器提升逻辑，递归搜索已知路径。

**可能追问**：

- Q: 你是怎么排查这些 bug 的？
  A: 第一个 bug：打印 LLM 原始返回，发现 trailing comma，加了 `re.sub(r',\s*([}\]])', r'\1', text)` 清理。第二个 bug：打印 PDF 底层字体信息，发现没有注册 CJK 字体。第三个 bug：打印 API 原始 JSON 结构，发现字段路径和代码中假设的不一致。

---

### 9.12 扩展性类

**Q: 如果要新增一种招聘平台，需要改哪些文件？**

A: 两步。第一，在 `platform_crawler_service.py` 中新增平台的爬取函数（搜索 URL 构建、API 响应解析、DOM 卡片提取）。第二，在 `PLATFORM_NAMES`、`PLATFORM_ALIASES`、`PLATFORM_LOGIN_URLS`、`CITY_CODES` 字典中新增对应条目。其他代码（前端、分析流程）不需要改——因为所有平台的输出都归一化为统一的 JobCard 格式。

**可能追问**：

- Q: 如果要新增一种评分维度呢？
  A: 在 `scoring_service.py` 中新增一个 `_score_xxx()` 函数，返回 (score, reason)。然后在 `compute_scores()` 中调用它，更新权重（四个权重必须加起来等于 1.0）。前端 `ScoreDetail` schema 和 Recharts 图表也需要同步更新。

- Q: 如果要支持英文简历呢？
  A: 需要改三个地方。第一，诊断规则中的正则模式需要补充英文模式（目前已部分支持，如 action keywords 有英文版）。第二，技能归一化词典需要补充更多英文变体（目前已有部分）。第三，Embedding 模型已经支持多语言（paraphrase-multilingual），不需要改。

---

### 9.13 产品思维类

**Q: 和市面上的简历工具比，你的差异化在哪？**

A: 市面上主要的竞品：超级简历（模板驱动，没有 AI 匹配和诊断）、各类 AI 简历生成器（一键生成但没有证据溯源，容易编造经历）、招聘平台的匹配（只是关键词匹配，没有多维度评分和可操作建议）。

我的差异化三点：第一，**证据约束改写**——防止 AI 编造，每个改写有溯源。第二，**四维评分 + 10 规则诊断**——不是给一个数字，是给一个可操作的改进方案。第三，**全流程 Agent**——从搜索岗位到面试准备，一个系统覆盖整个求职 workflow。

---

### 9.14 项目反思类

**Q: 这个项目如果要上线，还差什么？**

A: 几个关键缺口：
1. **异步任务队列**（Celery + Redis）——当前分析是同步的，大 PDF 可能超时
2. **用户认证**——JWT + OAuth，目前所有 API 公开访问
3. **Docker 化部署**——Docker Compose 一键启动
4. **评分模型验证**——积累标注数据，用真实用户反馈调优权重
5. **API 限流和错误监控**——特别是 LLM 调用成本控制
6. **国际化**——当前中文优先，英文简历支持弱

**Q: 你在项目中学到了什么？**

A: 技术层面：学会了 FastAPI + Pydantic 做类型安全的 API 开发、SQLAlchemy 2.0 ORM、LLM prompt engineering 和输出校验、Playwright 浏览器自动化、PDF 生成中的 CJK 字体处理。

工程层面：学会了在规则和 LLM 之间做权衡——不是所有场景都适合 AI，确定性场景用规则更好；学会了防 LLM 幻觉的系统设计——不是靠更好的 prompt 来解决，而是靠系统架构（证据约束 + 校验 + fallback）。

产品层面：学会了从用户视角思考——不是"我能做什么功能"，而是"用户投简历时遇到什么问题"。证据约束功能就是发现市面工具都在编造经历后才设计的。

---

## 十、简历包装

### 10.1 项目描述（简历用）

**简历-JD 智能匹配分析系统** | 独立开发 | Python + FastAPI + React + MySQL

- 独立设计并开发面向求职场景的多 Agent AI 系统，后端基于 FastAPI + SQLAlchemy 2.0 + Pydantic v2，前端基于 React 18 + TypeScript + Tailwind CSS，实现从 PDF 简历上传到可解释分析报告的端到端流程
- 设计四维度加权评分模型（技能匹配 40% + 项目相关性 25% + 语义相似度 20% + 硬性要求 15%），实现 200+ 技能别名归一化引擎覆盖 8 个技术类别，技能匹配准确率相比纯字符串匹配显著提升
- 实现 10 条规则的简历诊断引擎，检测缺失技能、模糊描述、缺少量化指标等问题，每条规则输出问题类型、严重程度、原文证据和改进建议
- 设计证据约束的 AI 简历改写机制，通过 resume_evidence + jd_evidence 双证据链和风险判定矩阵防止 LLM 编造经历，集成质量门禁（5 项确定性检查）确保改写结果可直接投递
- 集成 sentence-transformers 多语言 Embedding 模型计算语义相似度，同时实现 TF-IDF 降级方案，确保无 GPU 环境可运行；设计 Mock/LLM 双模式架构保证系统在无 API Key 环境下可独立运行
- 基于 Playwright 实现 BOSS 直聘、智联招聘、猎聘、前程无忧四平台岗位爬虫，采用 API 拦截 + DOM 提取双通道策略，支持 DB 搜索缓存（命中时 < 1 秒返回 vs. 重新爬取 1-6 分钟）
- 实现 AI 模拟面试功能（面试题生成 + AI 对话 + 答案评分）和 Word/PDF 报告导出（CJK 字体处理 + emoji 清洗）

### 10.2 技术亮点

1. **规则 + LLM 混合系统**：该确定的地方用规则（评分/诊断），该灵活的地方用 LLM（改写/面试），有序 fallback 而非二选一
2. **证据约束机制**：自己发现的问题 + 自己设计的方案，防止 AI 编造经历
3. **Agent 非框架**：不用 LangChain 实现 Agent，体现对概念的理解而非框架熟练度
4. **工程化细节**：技能归一化、PDF CJK 字体、CDP 进程管理、前端容错——真实项目才有的 dirty work
5. **多平台适配**：四个招聘平台的适统的 JobCard 格式

### 10.3 可能追问及应对

| 追问方向 | 应对策略 |
|---------|---------|
| "为什么不用 LangChain？" | 强调 Agent 本质是概念不是框架，不用框架体现对概念的理解 |
| "评分模型怎么验证的？" | 承认目前缺乏标注数据，是基于规则设计 + 人工 bad case 调优 |
| "LLM 成本怎么控制？" | 承认当前没有做成本控制，计划用缓存 + 限流 + 异步队列 |
| "和 XX 竞品比有什么优势？" | 聚焦证据约束改写——这是市面工具都没有的功能 |
| "项目有什么不足？" | 主动说：同步流程、中文优先、无认证、固定权重——展示自我认知 |

---

## 附录 A：API 端点清单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/resumes/list` | 简历列表 |
| POST | `/api/v1/resumes/upload` | 上传简历 PDF |
| POST | `/api/v1/resumes/{id}/parse` | 解析简历 |
| GET | `/api/v1/jds/list` | JD 列表 |
| POST | `/api/v1/jds/` | 创建 JD |
| POST | `/api/v1/jds/{id}/parse` | 解析 JD |
| POST | `/api/v1/jds/platforms/search` | 搜索岗位 |
| POST | `/api/v1/analysis/run` | 运行分析 |
| GET | `/api/v1/analysis/history/list` | 分析历史 |
| GET | `/api/v1/analysis/{task_id}` | 分析详情 |
| POST | `/api/v1/analysis/{task_id}/rewrite` | 项目级改写 |
| POST | `/api/v1/analysis/{task_id}/full-rewrite` | 整份简历改写 |
| POST | `/api/v1/analysis/{task_id}/interview-questions` | 生成面试题 |
| GET | `/api/v1/analysis/{task_id}/report` | 获取报告 |
| GET | `/api/v1/analysis/{task_id}/export/word` | 导出 Word |
| GET | `/api/v1/analysis/{task_id}/export/pdf` | 导出 PDF |
| POST | `/api/v1/interview/score` | 评分单个答案 |
| POST | `/api/v1/interview/start` | 开始模拟面试 |
| POST | `/api/v1/interview/chat` | 面试对话 |

## 附录 B：评分公式速查

```
total_score = skill_score × 0.40 + project_score × 0.25
            + semantic_score × 0.20 + requirement_score × 0.15

skill_score = min(100, req_ratio × 90 + pref_bonus)
  req_ratio = |matched_required| / |jd_required|
  pref_bonus = (|matched_preferred| / |jd_preferred|) × 10

project_score = avg(各项目分数)
  项目分数 = tech_overlap(40) + action_keywords(30) + metrics(20) + length(10)
  无量化指标 → 上限 60

semantic_score = 35 + 60 × √(cosine_similarity) × 0.62 + keyword_score × 0.38

requirement_score = avg(各检查项)
  满足=100, 未知=60, 不满足=30
```

## 附录 C：项目文件结构

```
ResumeMatch-AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/       # 4 个路由模块
│   │   ├── core/                   # config.py, database.py, exceptions.py
│   │   ├── models/                 # 7 个 SQLAlchemy 模型
│   │   ├── schemas/                # 12 个 Pydantic schema
│   │   ├── services/               # 18 个业务服务
│   │   ├── prompts/                # 8 个 LLM prompt 模板
│   │   └── utils/                  # pdf_parser, prompt_render, model_dump
│   ├── data/samples/               # 示例 JD 和简历
│   ├── tests/                      # 单元测试
│   ├── main.py                     # 后端入口
│   └── requirements.txt            # Python 依赖
├── frontend/
│   └── src/
│       ├── api/                    # 5 个 API 模块
│       ├── components/             # 14 个 UI 组件
│       ├── pages/                  # 7 个页面
│       └── types/                  # 4 个类型定义
├── job_crawler/                    # 独立岗位爬虫
├── browser-extension/              # 浏览器插件
└── docs/                           # 设计文档
```
