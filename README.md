# ResumeMatch AI

[简体中文](README.md) | [English](README.en.md)

把一份简历和一个目标岗位放在一起，找出匹配依据、技能缺口和表达问题，再进入简历改写与模拟面试。适合求职者围绕**一个具体岗位**准备材料，也适合观察规则评分、模型分析和浏览器岗位采集怎样协作。

核心输入是 **PDF 简历 + JD 正文**。输出包括四维匹配报告、改写稿和面试反馈；报告可导出 Word / PDF，改写稿可编辑后导出 TXT / PDF / Word。项目不替你自动投递，也不能把生成建议变成实际经历。

[本机启动](#本机启动) · [完成一次匹配](#从简历到第一份报告) · [改写与面试](#继续改写或练习面试) · [原理](#匹配与改写怎样工作) · [采集扩展](#岗位采集与浏览器扩展)

## 本机启动

准备 Python 3.11、Node.js 20 / 22、MySQL 8。先采用 mock 规则模式，不需要模型 Key；岗位浏览器与扩展可以稍后配置。

### 获取代码与准备数据库

```bash
git clone https://github.com/kayaduster607-jpg/ResumeMatch-AI.git
cd ResumeMatch-AI
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS resume_match CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

为应用准备能访问这个库的 MySQL 账号。连接串形如 `mysql+pymysql://resume_user:YOUR_PASSWORD@127.0.0.1:3306/resume_match?charset=utf8mb4`，其中用户与密码要替换为自己创建的账号，特殊字符需 URL 编码。

### 启动后端

Windows PowerShell，从项目根目录进入 backend：

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$dbConnection = Read-Host "MySQL connection URL" -AsSecureString
$env:DATABASE_URL = [System.Net.NetworkCredential]::new("", $dbConnection).Password
$env:LLM_PROVIDER = "mock"
$env:LLM_STRICT_MODE = "false"
$env:DEBUG = "false"
.\.venv\Scripts\python.exe main.py
```

打开 [http://localhost:9000/health](http://localhost:9000/health) 检查服务，再查看 [API 文档](http://localhost:9000/docs)。缺 Key 时必须显式选择 mock，代码默认使用真实服务且开启严格模式。

### 启动前端

另开终端，从仓库根目录运行：

```bash
cd frontend
npm ci
npm run dev
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。开发代理把 `/api` 请求交给 9000 端口。

## 从简历到第一份报告

1. 进入 `/upload`，上传一份不超过 10 MB、能提取文字的 PDF 简历。可将 [示例简历文本](backend/data/samples/sample_resume.txt)另存为 PDF；网页上传框不接收这个 TXT。
2. 进入 `/jd`，先选手动粘贴，把 [Python 后端实习岗位示例](backend/data/samples/jd_backend_intern.txt)填入完整 JD。无需先配置招聘平台采集。
3. 在 `/analysis` 选择刚保存的简历和岗位，开始分析。上传成功只代表材料已接收，等待匹配任务完成后再进入报告。
4. 报告页的路径为 `/report/<taskId>`，使用程序返回的任务 ID。查看各维度评分、命中 / 缺失技能、问题依据和建议。
5. 点击“导出 Word”或“导出 PDF”，在浏览器下载目录打开文件，核对内容与当前任务一致。

| 输入 / 操作 | 中间结果 | 最终结果 |
| --- | --- | --- |
| PDF 简历 | 结构化信息与简历 ID | 可选择的分析材料 |
| 岗位 JD 正文 | 结构化岗位与岗位 ID | 目标要求 |
| 对简历与岗位发起分析 | 任务状态、分项评分与依据 | 网页报告、Word / PDF |

例如，岗位要求 Python、FastAPI、SQL 和接口开发时，应检查报告怎样把简历证据映射到这些要求，而不是只看总分。mock 用规则输出，真实模型的表达质量需另行验证。

## 继续改写或练习面试

- 在 `/rewrite/<taskId>` 生成改写，先检查策略与证据，再手动编辑和导出。缺少依据的指标需要本人确认，不要直接接受新增数字。
- 在 `/interview/<taskId>` 查看针对该岗位的问题，输入自己的回答后评分；需要时继续多轮追问并看总结。

匹配报告、改写和题库保存到 MySQL，下载文件保存到浏览器指定目录。面试历史由页面传回后端，当前不应按完整持久会话系统理解。

## 匹配与改写怎样工作

![前端、分析服务与 MySQL](docs/assets/architecture.png)

评分由技能匹配 40%、项目相关性 25%、文本相似度 20%、学历 / 经验 15% 组成。技能别名先归一化，减少“同一技术不同写法”的漏匹配；问题诊断再定位技能缺口、模糊描述、角色不清与缺量化依据。

整份改写保留策略和证据链，清洗技术栈与夸大措辞；模型生成仍需人工核实。React 负责材料与报告交互，FastAPI 组织解析、分析、导出及面试，MySQL 保存结构化结果和任务快照。


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



## 常见问题

| 现象 | 优先检查 |
| --- | --- |
| 后端启动或分析失败 | MySQL 连接、库权限、Python 3.11 依赖，以及是否显式设置 mock |
| PDF 解析为空 | 文档是否只有扫描图片；先换文字型 PDF 核对流程 |
| 前端打开但 API 失败 | 后端是否监听 9000，开发代理是否仍指向该地址 |
| 扩展连接不上 | 默认是 8000，须同时调整设置、默认地址和 host permission |
| 部署静态前端后路由或 API 失效 | 配置 SPA 回退与 `/api` 反向代理，Vite 开发代理不会进入 dist |

## 开发入口

完整接口在运行中的 `/docs`。简历上传、JD、分析与导出均位于 `/api/v1`，下表用于按功能定位：


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
