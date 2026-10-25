<div align="center">

# ResumeMatch-AI

**读懂岗位要求，找到简历差距，把已有经历讲清楚。**

从 PDF 简历与职位描述出发，连接匹配分析、证据约束改写和模拟面试。

![React](https://img.shields.io/badge/React-18-149ECA?style=flat-square&logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-browser_automation-2EAD33?style=flat-square)

[项目亮点](#项目亮点) · [系统架构](#系统架构) · [快速开始](#快速开始) · [配置说明](#配置说明) · [开发与验证](#开发与验证)

</div>

![ResumeMatch-AI 系统架构](docs/assets/architecture.png)

ResumeMatch-AI 是面向求职者的简历与 JD（职位描述）匹配工具。上传简历、粘贴或导入岗位后，可以查看分项评分、技能差距和问题证据，再生成可编辑的简历改写稿，并围绕同一岗位进行面试练习。

项目采用 **规则评分 + 文本相似度 + LLM 分析与生成** 的组合：评分权重写在代码中，改写后执行质量检查，面试可以沿用原简历或改写版本。适合个人求职辅助、本地演示和全栈 AI 应用学习。

## 先用一次：简历和岗位输入后，结果在哪里

| 你需要准备 | 系统接收什么 | 你最终得到什么 |
| --- | --- | --- |
| 一份简历 | 网页上传PDF，最大10MB；扫描件不等于可提取文本 | 结构化简历信息与简历ID |
| 一份目标岗位 | 岗位名称、公司名称可选信息，以及完整JD正文 | 结构化岗位信息与岗位ID |
| 一次匹配任务 | 选择刚才的简历与岗位后开始分析 | 评分、缺口诊断、建议、改写和面试练习 |

### 第一次操作，照这条路径走

1. 先完成后文[快速开始](#快速开始)的MySQL、后端和前端安装。没有模型Key时使用 `LLM_PROVIDER=mock`；这是规则演示，不是真实模型效果。
2. 打开 `http://127.0.0.1:5173/upload`，上传自己的PDF。没有测试PDF时，可把[示例简历文本](backend/data/samples/sample_resume.txt)另存为PDF；不要直接把TXT传进网页上传框。
3. 进入 `/jd`，先选**手动粘贴JD**，把[后端实习岗位示例](backend/data/samples/jd_backend_intern.txt)复制到完整JD输入框。第一次使用不需要开启招聘平台采集。
4. 进入 `/analysis`，选择刚保存的简历与JD，开始分析。成功后记录任务ID，进入 `/report/<taskId>`；URL里的ID由程序返回，不是固定示例数字。
5. 在报告页查看分项评分与问题，点击“导出 Word”或“导出 PDF”。下载文件进入浏览器下载目录；分析记录同时保存在MySQL。
6. 需要改简历时，进入 `/rewrite/<taskId>`，先生成、再核对和编辑，最后导出TXT/PDF/Word。需要练习时进入 `/interview/<taskId>`，输入自己的回答后查看反馈。

**一个具体输入：**“Python后端实习生；需要Python、FastAPI、SQL和接口开发经验”是JD正文；简历输入则是PDF文件。输出是匹配分析和建议，系统不会替你投递岗位，也不能把生成建议当成你实际做过的经历。

**怎样确认完成：**报告页有当前任务的数据，下载文件能够打开；只看到文件上传成功或拿到resume_id，不代表匹配分析已经完成。网页上传格式与CLI支持格式不同，详见后文。

## 项目亮点

| 能力 | 具体实现 |
| --- | --- |
| 可解释的四维评分 | 技能匹配 40%、项目相关性 25%、文本相似度 20%、学历/经验要求 15%；返回各维度理由与命中/缺失技能 |
| 技能别名归一化 | 将不同拼写和别名映射到统一技能，减少简历和 JD 表述差异造成的漏匹配 |
| 带证据的问题诊断 | 检查缺少必备技能、项目描述模糊、缺少量化指标、角色不清晰等问题，并生成建议 |
| 证据约束的整份改写 | 展示改写策略和证据链；清洗技术栈、调整夸大措辞，对原文中找不到的量化指标提示人工确认 |
| 连续的面试准备流程 | 针对选定简历与 JD 生成题库、评分单题回答、进行多轮追问并生成面试总结 |
| 岗位发现与导入 | Web 端支持四个平台的搜索、筛选、缓存与导入；另提供独立 CLI 和可选浏览器扩展 |
| 多格式输出 | 匹配报告导出 Word/PDF，改写简历支持编辑及 TXT/PDF/Word 输出，CLI 岗位结果支持 JSON/CSV/Markdown/XLSX |
| 无 API Key 的体验入口 | 显式开启 `mock` 后，可用规则流程体验核心功能；真实模型用于更丰富的分析、改写和面试 |

## 使用流程

```mermaid
flowchart LR
    A[上传 PDF 简历] --> C[结构化解析]
    B[粘贴 / 导入岗位 JD] --> C
    C --> D[四维评分与问题诊断]
    D --> E[查看与导出报告]
    E --> F[生成改写稿 / 检查证据]
    F --> G[编辑并导出简历]
    G --> H[针对岗位模拟面试]
    classDef input fill:#eff6ff,stroke:#93c5fd,color:#1e3a8a
    classDef core fill:#ecfdf5,stroke:#6ee7b7,color:#065f46
    classDef result fill:#f5f3ff,stroke:#c4b5fd,color:#5b21b6
    class A,B input
    class C,D core
    class E,F,G,H result
```

Web 页面依次为 `/upload`、`/jd`、`/analysis`、`/report/:taskId`、`/rewrite/:taskId` 和 `/interview/:taskId`。Web 上传入口接受 **不超过 10 MB 的 PDF**；CLI 的简历输入另支持 TXT/PDF/DOCX。

## 系统架构

上方架构图提供 [SVG 矢量原稿](docs/assets/architecture.svg) 和 [绘图脚本](docs/assets/generate_architecture.py)，便于随代码演进更新。

| 层级 | 职责与主要技术 |
| --- | --- |
| 页面层 | React 18、TypeScript、Vite 6、Tailwind CSS、React Router、Axios；组织上传、分析、改写和面试流程 |
| API 层 | FastAPI、Pydantic v2；业务接口统一位于 `/api/v1`，通过 SQLAlchemy 2.0 访问 MySQL |
| 业务层 | 简历/JD 解析、技能归一化、四维评分、问题诊断、报告、改写质量检查、面试服务 |
| 模型层 | DeepSeek / OpenAI / OpenAI-compatible 客户端；`mock` 规则模式；sentence-transformers 与轻量文本匹配回退 |
| 采集层 | Playwright + Microsoft Edge CDP；支持 BOSS 直聘、智联招聘、猎聘、前程无忧，另有独立 CLI |
| 文件层 | PyMuPDF 文本提取、python-docx、ReportLab；扫描 PDF 可选接入 Tesseract OCR |

**评分与生成分开。** `scoring_service.py` 负责固定权重聚合，`diagnosis_service.py` 负责问题诊断，LLM 服务负责结构化抽取和内容生成。分数仍会受上游解析结果及文本相似度实现影响；它表示本系统的匹配启发式，不代表招聘方录用概率。

**文本匹配按本地条件选择实现。** 已有模型缓存时尝试 sentence-transformers，否则使用轻量词频向量余弦相似度回退。回退类名虽然是 `TFIDFEmbeddingService`，当前计算并未使用 IDF 权重，此处按实际实现描述。

**改写保留人工复核入口。** LLM 或规则生成结果统一经过 `resume_rewrite_quality.py`，输出策略、证据链和质量检查结果。检查可以提示风险，最终投递前仍需核实经历与数字。

### 匹配分析的数据流

```mermaid
sequenceDiagram
    autonumber
    participant UI as React 页面
    participant API as FastAPI
    participant Parse as 解析服务
    participant Match as 评分 / 诊断
    participant AI as LLM / mock
    participant DB as MySQL
    UI->>API: 上传 PDF / 创建 JD
    API->>DB: 保存原文
    UI->>API: POST /api/v1/analysis/run
    opt 尚未完成结构化解析
        API->>Parse: 解析简历与 JD
        Parse->>AI: 结构化抽取 / 规则解析
        Parse->>DB: 保存 parsed_json
    end
    API->>Match: 归一化技能、计算分数、诊断问题
    Match-->>API: 维度分、技能差距、问题证据
    API->>AI: 生成补充分析
    API->>DB: 保存任务与报告
    API-->>UI: 展示匹配报告
```

## 快速开始

推荐 **Python 3.11 + Node.js 20/22 + MySQL 8**。后端依赖锁定了 `numpy==1.26.4` 等版本，请优先使用 Python 3.11 创建环境。只有使用岗位采集时才需要浏览器运行环境。

### 1. 克隆项目并创建数据库

```bash
git clone https://github.com/kayaduster607-jpg/ResumeMatch-AI.git
cd ResumeMatch-AI
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS resume_match CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

建议为应用单独创建数据库用户，并将连接信息填写到下一步的本地配置文件中。

### 2. 安装后端并配置规则模式

Windows PowerShell：

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 手动创建 backend/.env，填写下方最小配置后再启动。
.\.venv\Scripts\python.exe main.py
```

macOS / Linux（从仓库根目录开始）：

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
# 手动创建 backend/.env，填写下方最小配置后再启动。
.venv/bin/python main.py
```

`backend/.env` 最小配置（替换数据库账号、密码）：

```dotenv
DATABASE_URL=mysql+pymysql://resume_user:YOUR_PASSWORD@127.0.0.1:3306/resume_match?charset=utf8mb4
LLM_PROVIDER=mock
LLM_STRICT_MODE=false
DEBUG=false
```

后端默认监听 `0.0.0.0:9000`。本机访问 [健康检查](http://localhost:9000/health) 或 [交互式 API 文档](http://localhost:9000/docs)。数据库密码包含 `@`、`#` 等特殊字符时，需要先进行 URL 编码。

> 代码默认使用 `deepseek` 且严格模式开启。没有 API Key 时，务必显式设置 `LLM_PROVIDER=mock`。`mock` 使用规则输出，与真实模型的生成质量和能力不同。

### 3. 启动前端

在另一个终端中，从仓库根目录运行：

```bash
cd frontend
npm ci
npm run dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。Vite 将 `/api` 请求代理到 `http://localhost:9000`。先上传 PDF，再粘贴一份 JD，完成第一次分析。

`backend/data/samples/` 提供示例简历文本、三类岗位描述与示例报告。示例中的经历、指标和报告分数用于演示，不是本项目的性能测试结果；示例简历的联系方式为占位内容。Web 上传需自行将文本另存为 PDF。

## 配置说明

所有密钥只放在本地配置或部署环境中。公开仓库不包含任何 `.env` 文件。

| 变量 | 用途 | 代码默认值 |
| --- | --- | --- |
| `DATABASE_URL` | MySQL 连接串 | 本机 `resume_match` 的占位连接串，需自行设置 |
| `LLM_PROVIDER` | `mock` / `deepseek` / `openai` / `openai_compatible` | `deepseek` |
| `LLM_STRICT_MODE` | 真实模型失败时在支持此开关的流程中直接报错 | `true` |
| `DEEPSEEK_API_KEY` | DeepSeek 密钥 | 空 |
| `DEEPSEEK_BASE_URL` | DeepSeek 接口地址 | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | DeepSeek 模型名 | `deepseek-chat` |
| `OPENAI_API_KEY` | OpenAI 或兼容服务密钥 | 空 |
| `OPENAI_BASE_URL` | OpenAI-compatible 服务地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | OpenAI-compatible 模型名 | `gpt-4o` |
| `EMBEDDING_MODEL` | 本地句向量模型名 | `paraphrase-multilingual-MiniLM-L12-v2` |
| `EDGE_PATH` | 自动定位失败时指定 Edge 可执行文件 | 空 |
| `EDGE_REMOTE_DEBUG_PORT` | Edge CDP 端口 | `9333` |
| `CORS_ORIGINS` | 允许的前端来源，JSON 数组 | `localhost:5173` 与 `127.0.0.1:5173` |
| `DEBUG` | 调试日志和数据库 SQL 日志 | `true`；处理真实简历时建议设为 `false` |

启用 DeepSeek 时，将规则模式的两项配置替换为：

```dotenv
LLM_PROVIDER=deepseek
LLM_STRICT_MODE=true
DEEPSEEK_API_KEY=YOUR_API_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

使用其他兼容服务时，设置 `LLM_PROVIDER=openai_compatible`，填写 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LLM_MODEL`。以上模型名来自项目代码默认配置，实际可用性以所接入服务为准。

## 岗位采集与浏览器扩展

### Web 端岗位搜索

在 `/jd` 页面打开项目专用 Edge，手动登录目标平台、保存登录态后搜索。可按关键词、城市、经验、学历等筛选，并将岗位导入 JD。搜索结果写入 MySQL 缓存；前端另有本地缓存，可通过强制刷新重新采集。

Web 采集依赖本机 Microsoft Edge；CLI 首次使用前，在已安装项目依赖的 Python 环境中执行 `python -m playwright install chromium`。平台可能要求手动登录或验证，页面与接口变化也可能影响采集。请遵守平台使用规则，使用合理的采集频率。

### 独立 CLI

在仓库根目录、使用已安装后端依赖的环境运行：

```bash
python -m job_crawler login --platforms all
python -m job_crawler run --resume backend/data/samples/sample_resume.txt --keyword "Python 后端实习生" --city "广州" --platforms all --pages 1 --min-score 50 --top 50
```

Windows 使用 `backend\.venv\Scripts\python.exe`，macOS/Linux 使用 `backend/.venv/bin/python` 替换命令中的 `python`，即可复用前面的环境。运行 `python -m job_crawler --help` 查看参数。

默认输出目录为 `outputs/job_crawler/`，包含 JSON、CSV、Markdown，`openpyxl` 可用时另导出 XLSX。CLI 与 Web 的采集/排序入口相互独立，两者分数不应视为严格等价。

### 可选浏览器扩展

通过 Chrome/Edge 的“加载已解压的扩展程序”载入 `browser-extension/`。当前扩展的 `popup.js` 和 `manifest.json` 默认后端地址/权限是 **`localhost:8000`**，主服务使用 **`9000`**；使用前需将扩展设置、默认地址及 host permission 一并对齐到 `http://localhost:9000`，然后重新加载。详见 [扩展说明](browser-extension/README.md)。

## 数据与部署

| 数据 | 保存位置 | 说明 |
| --- | --- | --- |
| 简历与 JD | MySQL：`resumes`、`job_descriptions` | 原文及结构化 JSON |
| 分析与报告 | MySQL：`analysis_tasks`、`match_reports` | 任务状态、维度评分和报告快照 |
| 改写与题库 | MySQL：`rewritten_resumes`、`interview_questions` | 生成内容、用户编辑稿与题库记录 |
| 岗位缓存 | MySQL：`cached_job_searches` | 搜索条件、岗位结果与错误信息 |
| 浏览器登录状态 | `.job_browser/`、`.job_crawler/`，相对位置取决于启动目录 | 私有运行数据，不应提交或共享 |
| 前端临时状态 | 浏览器 localStorage / 页面内状态 | 部分缓存保留在浏览器；面试历史由页面传回后端，不是持久会话系统 |

当前后端**要求 MySQL，不支持 SQLite**。启动时执行 `Base.metadata.create_all()`，只创建缺失表，不负责已有表的版本迁移。备份和迁移时应单独维护 MySQL 数据；重新克隆代码不会恢复分析记录。

项目适合本地或受控单实例部署，目前没有容器配置、账号体系或访问权限隔离。后端默认监听所有网卡，部署时应限制网络访问；真实模型模式会向配置的模型服务发送相关简历/JD/回答内容。不要将未经授权的个人材料用于公开演示。

前端静态构建使用 `npm run build`，产物位于 `frontend/dist/`。通过静态服务器部署时，需配置 SPA 路由回退，并将 `/api` 反向代理到后端；Vite 的开发代理不会自动包含在构建产物中。

## API 概览

除 `/health` 外，下表路径均相对于 `/api/v1`。完整请求结构和响应以运行中的 [Swagger UI](http://localhost:9000/docs) 为准。

| 模块 | 代表接口 | 功能 |
| --- | --- | --- |
| 简历 | `POST /resumes/upload` · `POST /resumes/{id}/parse` | 上传 PDF、解析 |
| JD | `POST /jds` · `POST /jds/{id}/parse` | 创建并解析职位描述 |
| 平台搜索 | `POST /jds/platforms/search` | 搜索岗位并排序 |
| 分析 | `POST /analysis/run` · `GET /analysis/history/list` | 执行分析、查询历史 |
| 报告 | `GET /analysis/{id}/report` · `GET /analysis/{id}/export/word` | 获取报告、导出 Word；另有 PDF 导出 |
| 改写 | `POST /analysis/{id}/full-rewrite` · `PUT /analysis/{id}/full-rewrite` | 生成改写、保存编辑 |
| 题库 | `POST /analysis/{id}/interview-questions` · `POST /interview/score` | 生成题库、单题评分 |
| 多轮面试 | `POST /interview/start` · `/interview/chat` · `/interview/finish` | 启动、追问、结束总结 |

## 开发与验证

从仓库根目录使用后端虚拟环境运行单元测试，`pytest` 需额外安装：

```bash
python -m pip install pytest==8.3.4
cd backend
python -m pytest
```

同 CLI 示例一样，将 `python` 替换为相应的虚拟环境解释器路径，或先激活后端虚拟环境。主要覆盖评分、技能归一化、JD 规则解析、诊断和改写质量检查。发布验证范围见 [验证记录](docs/validation.md)。

前端类型检查与生产构建：

```bash
cd frontend
npm ci
npm run build
```

修改评分时，应同步检查 `scoring_service.py` 的权重与对应测试；修改改写流程时，应保留原始经历、岗位要求和生成内容的证据边界。

## 项目结构

```text
ResumeMatch-AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # 简历、JD、分析、面试接口
│   │   ├── core/                # 配置、数据库和异常
│   │   ├── models/              # SQLAlchemy 数据模型
│   │   ├── schemas/             # Pydantic 请求/响应结构
│   │   ├── services/            # 评分、诊断、改写、面试及采集
│   │   ├── prompts/             # 模型提示词模板
│   │   └── utils/               # PDF 提取、字体与导出工具
│   ├── data/samples/            # 演示材料
│   ├── tests/                   # 服务层单元测试
│   ├── main.py                  # 后端入口，9000 端口
│   └── requirements.txt
├── frontend/src/
│   ├── api/                     # Axios 接口封装
│   ├── components/              # 报告、评分、表单等组件
│   ├── pages/                   # 求职辅助流程页面
│   └── types/                   # TypeScript 类型
├── job_crawler/                 # 独立岗位采集与导出 CLI
├── browser-extension/           # 可选 Manifest V3 扩展
├── docs/assets/                 # 架构图与绘图源码
└── start_*.bat / start_*.sh      # 本地启动脚本
```

## 后续方向

以下是可扩展方向，尚未作为现有能力交付：账号与数据隔离、Alembic 数据迁移、耗时任务后台化、模型输出稳定性评估、统一扩展端口配置，以及可复现的匹配效果评测集。

扫描 PDF OCR 还需额外安装 `pytesseract`、Pillow、系统 Tesseract 及中文语言包。岗位采集依赖外部平台，不能保证持续可用。项目当前未附独立 `LICENSE` 文件；公开可见不等于已授予某种开源许可，使用或再分发前请与维护者确认。

进一步阅读：[改写策略与质量检查](docs/resume-rewrite-skill-integration.md) · [浏览器扩展](browser-extension/README.md)。
