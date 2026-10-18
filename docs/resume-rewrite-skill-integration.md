# 简历改写 Skill 接入说明

## 1. 接入目标

将人工简历修改流程固化到 ResumeMatch-AI 的整份简历改写链路中，使系统不再只是"根据 JD 生成一份文本"，而是按照可复用的简历优化流程进行：

1. 目标岗位建模：抽取岗位硬技能、项目证据、业务场景、硬性条件。
2. 候选人事实证据盘点：只使用原简历、结构化简历和项目事实作为经历依据。
3. 项目经历重写：统一使用"项目简介 → 技术栈 → 技术亮点"。
4. 技术栈清洗：去除 GitHub、Repo、URL、README、过细依赖等非技术栈内容。
5. 量化真实性校验：真实数字保留，未验证数字标记人工确认。
6. 实习生语气控制：避免无证据使用"主导、精通、架构师、负责人"等过度表述。
7. 证据约束：区分 resume evidence 和 JD evidence，JD 证据不能证明候选人做过某事。
8. 质量门禁：输出直接投递格式、技术栈、语气、量化数据、证据链等检查结果。

## 2. 改动范围

| 层级 | 文件 | 作用 |
|---|---|---|
| Schema | `backend/app/schemas/rewrite_resume.py` | 新增 `RewriteStrategy`、`RewriteQualityGateItem`，`RewrittenResumeData` 增加 `rewrite_strategy` 与 `quality_gate` |
| Prompt | `backend/app/prompts/full_resume_rewrite.md` | 注入通用简历优化流程，要求项目经历按"项目简介/技术栈/技术亮点"输出，并声明技术栈、量化、实习生语气规则 |
| Service | `backend/app/services/resume_optimization_skill.py` | 复用型简历改写规则：技术栈清洗、项目块生成、指标抽取、语气改写、Prompt 指南 |
| Service | `backend/app/services/resume_rewrite_quality.py` | LLM/规则改写后的质量门禁：清洗技术栈、生成策略说明、检查新增指标与夸大表述、重评证据链风险 |
| Service | `backend/app/services/resume_rewrite_service.py` | 在 LLM 与规则回退模式后统一执行 `post_process_rewritten_resume()`；规则模式项目经历改为简历式结构 |
| Frontend Type | `frontend/src/api/analysisApi.ts` | 增加改写策略与质量门禁类型 |
| Frontend UI | `frontend/src/pages/RewritePage.tsx` | 在改写页面展示"改写策略与质量检查"，保留证据链双色卡片 |
| Test | `backend/tests/test_resume_rewrite_quality.py` | 覆盖技术栈清洗、质量门禁生成、未验证量化指标风险重评 |

## 3. 数据结构

### 3.1 RewriteStrategy

用于解释系统本次如何改写，而不是黑盒生成：

```json
{
  "target_role": "AI Agent 应用开发实习生",
  "role_requirements": ["Python", "FastAPI", "RAG"],
  "evidence_summary": ["命中技能：Python、FastAPI"],
  "section_order": ["个人信息", "求职意向", "专业技能", "项目经历"],
  "project_style": "项目简介 → 技术栈 → 技术亮点",
  "tech_stack_rules": ["技术栈不写 GitHub/Repo/过细依赖"],
  "quantification_rules": ["量化数据必须来自原文"],
  "tone_rules": ["实习生定位避免无证据拔高"],
  "omitted_or_compressed": ["因弱相关或缺证据而压缩的内容"]
}
```

### 3.2 RewriteQualityGateItem

用于暴露改写结果的风险与质量状态：

```json
{
  "name": "量化数据真实性",
  "status": "warning",
  "message": "存在原简历未出现的数字/指标，需人工确认：30%"
}
```

## 4. 关键规则

### 4.1 技术栈清洗

错误写法：

```text
技术栈：Next.js、TypeScript、pdf-parse、SheetJS、bcryptjs、Repo：https://github.com/xxx
```

清洗后：

```text
技术栈：Next.js、TypeScript、PDF 解析、Excel / CSV 解析、密码加密 / Cookie Session
```

### 4.2 项目经历结构

统一格式：

```text
项目名称｜角色
项目简介：一句话说明业务场景或项目目标。
技术栈：核心语言、框架、数据库、AI/RAG/Agent、工程能力。
技术亮点：
- 动作 + 技术实现 + 结果/约束
- 动作 + 架构设计 + 可验证指标
- 动作 + Bad Case 修复 / 评测 / 部署
```

### 4.3 证据风险判定

| 情况 | 处理 |
|---|---|
| 原简历项目中有事实证据 | 可低风险使用 |
| 只有技能区声明，项目没有体现 | 中风险，建议人工确认 |
| 只有 JD 需求，没有简历事实 | 高风险，不得直接写成经历 |
| 新增原文没有的量化指标 | 高风险，`fabrication_check=warning` |
| 把"参与"改成"主导"但原文无依据 | 高风险 |

## 5. 验证结果

已执行：

```bash
python -m compileall app
PYTHONPATH=. pytest -q tests/test_resume_rewrite_quality.py
```

结果：

```text
compileall: passed
test_resume_rewrite_quality.py: 3 passed
```

完整测试套件在项目开发环境安装 `requirements.txt` 后可执行：

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. pytest -q
```

## 6. 面试表达

可以这样讲：

> 我把人工简历修改流程接入到了 FullRewriteAgent，不只是让模型生成一份简历。系统会先做岗位建模和候选人事实证据盘点，再按"项目简介、技术栈、技术亮点"的结构改写项目经历。技术栈会清洗掉 GitHub、Repo、URL 和过细依赖；量化数据必须来自原简历或项目文档，新增数字会被质量门禁标记；同时继续使用 resume evidence / JD evidence 分离的证据链，避免把 JD 要求误写成候选人经历。
