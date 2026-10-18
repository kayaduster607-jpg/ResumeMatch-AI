# Full Resume Rewrite Prompt

## User Prompt Template
请基于以下信息，生成一份面向目标岗位的中文投递简历。

### 原始简历文本
{resume_text}

### 原始简历结构化信息
{resume_parsed}

### 目标岗位 JD 文本
{jd_text}

### 目标岗位结构化信息
{jd_parsed}

### 当前匹配情况
- 总分：{total_score}
- 匹配等级：{match_level}
- 已命中技能：{matched_skills}
- 缺失/弱体现技能：{missing_skills}
- 已发现问题：{problems}

### 改写要求
你要输出一份"可以直接投递"的中文简历，不是建议列表，不是分析报告。

硬性规则：
1. 原简历中已有的公司、学校、项目名称、工作经历、证书必须保留并加以利用。
2. 原简历有但表述不够好的内容，请你优化措辞、调整顺序、补充技术细节让它更贴近JD，而不是删掉。
3. [请补充：...]占位符只在原简历完全没有相关信息时才使用，且最多3处。
4. 优先把与目标JD匹配的真实经历前置展示；弱相关内容压缩或放到后面。
5. 项目经历必须包含：项目背景/你的具体职责/技术栈/关键动作/成果（原简历没写成果则根据技术栈合理推估，不要留空）。
6. 输出 full_text 时要使用清晰模块，适合 PDF/Word 导出。
7. 全文中文，技术名词可保留英文。
8. 不要输出"原简历未提供"这类描述——直接利用已有信息写出最好的版本。

{rewrite_guidelines}

### 建议简历结构
- 姓名与联系方式（原简历没有则用[请补充：手机号/邮箱]）
- 求职意向
- 个人优势
- 专业技能
- 项目经历
- 工作/实习经历（如有）
- 教育背景
- 证书/其他（如有）

### 证据约束（重要）
你必须为每一条改写后的关键描述（项目经历、个人优势、专业技能中的具体声明）提供证据链。
证据分为两类，不可混淆：

**resume_evidence（简历事实证据）** — 证明"我真的做过"
- source_type = "resume_project": 原始简历项目中的技术栈/描述/成果
- source_type = "resume_skill": 原始简历中的技能声明
- source_type = "resume_work_experience": 原始简历中的工作/实习经历
- source_type = "resume_education": 原始简历中的教育背景

**jd_evidence（JD 需求证据）** — 只说明"岗位需要什么"，不能证明我做过
- source_type = "jd_requirement": JD 中的必需技能/职责
- source_type = "jd_preferred": JD 中的加分项

关键原则：
- JD 写了"要求 Kubernetes"但你原简历没有 K8s 相关项目，改写结果里就算出现了 Kubernetes，也必须有 resume_evidence 支撑，否则就是编造
- 改写只是优化措辞、重组顺序、补充技术细节时 → risk = low
- 改写基于技术栈合理推估（如原项目用 Flask，改写为"Python Web 框架"）→ risk = medium
- 改写加入了原简历完全没有的新技能、新指标、新职责 → risk = high, fabrication_check = warning
- 把"参与"改成"主导"但原文无依据 → risk = high
- need_manual_confirm = true 当且仅当 risk = high 或 fabrication_check = warning 时

### 输出格式
只返回 JSON，schema 如下：
{
  "job_title": "目标岗位名称",
  "target_company": "目标公司；未知则为空字符串",
  "summary": "3-5行个人优势总结，必须贴合目标JD",
  "sections": [
    {"title": "模块标题", "content": "模块正文，多行文本"}
  ],
  "highlights": ["本次改写强化点1", "本次改写强化点2"],
  "full_text": "完整纯文本简历，按清晰模块排版，可直接复制投递",
  "changes_summary": "说明本次只做了哪些真实改写，没有编造哪些内容",
  "evidence_chain": [
    {
      "rewritten_bullet": "改写后的关键描述语句",
      "resume_evidence": [
        {
          "source": "project.项目名.tech_stack",
          "source_type": "resume_project",
          "field": "具体技术/技能名",
          "confidence": 0.92
        }
      ],
      "jd_evidence": [
        {
          "source": "jd.requirement",
          "source_type": "jd_requirement",
          "field": "Python 后端开发",
          "confidence": 0.85
        }
      ],
      "risk": "low",
      "fabrication_check": "passed",
      "need_manual_confirm": false
    }
  ]
}
