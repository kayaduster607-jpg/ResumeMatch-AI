# ResumeMatch AI

[简体中文](README.md) | [English](README.en.md)

Compare a resume with a target role to identify matching evidence, skill gaps, and weak wording, then continue with rewriting and mock interviews. It helps job seekers prepare for **one specific role**, and demonstrates how rule-based scoring, model analysis, and browser-based job collection work together.

Core input: **PDF resume + job-description text**. Outputs include a four-dimensional match report, a rewritten draft, and interview feedback. Reports export to Word / PDF; editable rewrites export to TXT / PDF / Word. The project does not apply for jobs automatically or turn generated suggestions into real experience.

[Start locally](#start-locally) · [First report](#from-resume-to-first-report) · [Rewrite and interview](#continue-with-rewriting-or-interview-practice) · [Design](#how-matching-and-rewriting-work) · [Job collection](#job-collection-and-browser-extension)

## Start locally

Prepare Python 3.11, Node.js 20 / 22, and MySQL 8. Start in rule-based mock mode without a model key; configure the job browser and extension later.

### Get the code and prepare MySQL

```bash
git clone https://github.com/kayaduster607-jpg/ResumeMatch-AI.git
cd ResumeMatch-AI
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS resume_match CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

Create a MySQL account with access to this database. A connection string looks like `mysql+pymysql://resume_user:YOUR_PASSWORD@127.0.0.1:3306/resume_match?charset=utf8mb4`. Replace the username and password with your own account; URL-encode special characters.

### Start the backend

In Windows PowerShell, enter backend from the project root:

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

Check [http://localhost:9000/health](http://localhost:9000/health), then open the [API docs](http://localhost:9000/docs). Explicitly choose mock if you have no key: code defaults to a real provider with strict mode enabled.

### Start the frontend

In another terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). The development proxy forwards `/api` requests to port 9000.

## From resume to first report

1. Open `/upload` and upload an extractable-text PDF resume no larger than 10 MB. You may save [sample resume text](backend/data/samples/sample_resume.txt) as PDF first; the web upload does not accept that TXT file directly.
2. At `/jd`, choose manual paste and enter the full [Python backend internship JD example](backend/data/samples/jd_backend_intern.txt). Recruitment-platform collection is not required first.
3. At `/analysis`, select the saved resume and role, then start analysis. Upload success means only that material was received; wait for matching to finish before opening the report.
4. The report route is `/report/<taskId>` using the returned task ID. Review dimension scores, matched / missing skills, evidence for issues, and recommendations.
5. Click “导出 Word” or “导出 PDF”, open the file in the browser's download directory, and check it belongs to the current task.

| Input / action | Intermediate result | Final result |
| --- | --- | --- |
| PDF resume | Structured information and resume ID | Selectable analysis material |
| JD text | Structured role and job ID | Target requirements |
| Analyze the resume against the role | Task state, dimension scores, evidence | Web report, Word / PDF |

For a role requiring Python, FastAPI, SQL, and API development, examine how resume evidence maps to those requirements rather than reading only the total score. Mock mode produces rule-based output; real-model wording quality requires separate validation.

## Continue with rewriting or interview practice

- Generate a rewrite at `/rewrite/<taskId>`, inspect its strategy and evidence, then edit and export it. Confirm unsupported metrics yourself; do not directly accept invented numbers.
- At `/interview/<taskId>`, view role-specific questions, enter your answers for scoring, and optionally continue follow-ups and a final summary.

Match reports, rewrites, and question banks are stored in MySQL; downloaded files go to the browser's selected directory. Interview history is passed back from the page to the backend and is not a fully persistent conversation system.

## How matching and rewriting work

![Frontend, analysis services, and MySQL](docs/assets/architecture.png)

Scores combine skill matching 40%, project relevance 25%, text similarity 20%, and education / experience 15%. Skill aliases are normalized to reduce missed matches from different names for the same technology. Diagnosis identifies skill gaps, vague descriptions, unclear roles, and missing quantitative evidence.

Full rewrites retain strategy and evidence chains and clean up technology lists and exaggerated wording; generated text still needs human verification. React handles materials and reports; FastAPI organizes parsing, analysis, export, and interviews; MySQL stores structured results and task snapshots.

## Configuration

Keep keys only in local configuration or deployment environments. The public repository includes no `.env` files.

| Variable | Purpose | Code default |
| --- | --- | --- |
| `DATABASE_URL` | MySQL connection string | Local `resume_match` placeholder; set your own |
| `LLM_PROVIDER` | `mock` / `deepseek` / `openai` / `openai_compatible` | `deepseek` |
| `LLM_STRICT_MODE` | Fail directly on real-model errors in workflows supporting this switch | `true` |
| `DEEPSEEK_API_KEY` | DeepSeek key | Empty |
| `DEEPSEEK_BASE_URL` | DeepSeek endpoint | `https://api.deepseek.com/v1` |
| `DEEPSEEK_MODEL` | DeepSeek model name | `deepseek-chat` |
| `OPENAI_API_KEY` | OpenAI / compatible service key | Empty |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `LLM_MODEL` | OpenAI-compatible model name | `gpt-4o` |
| `EMBEDDING_MODEL` | Local sentence-embedding model | `paraphrase-multilingual-MiniLM-L12-v2` |
| `EDGE_PATH` | Edge executable if autodetection fails | Empty |
| `EDGE_REMOTE_DEBUG_PORT` | Edge CDP port | `9333` |
| `CORS_ORIGINS` | Allowed frontend origins, JSON array | `localhost:5173` and `127.0.0.1:5173` |
| `DEBUG` | Debug and database SQL logging | `true`; use `false` for real resumes |

For DeepSeek, replace the two mock-mode settings with:

```dotenv
LLM_PROVIDER=deepseek
LLM_STRICT_MODE=true
DEEPSEEK_API_KEY=YOUR_API_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

For another compatible service, set `LLM_PROVIDER=openai_compatible`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `LLM_MODEL`. Model names above are code defaults; availability depends on your connected provider.

## Job collection and browser extension

### Web job search

At `/jd`, open the project's dedicated Edge browser, sign in manually, save login state, and search. Filter by keyword, city, experience, education, and more, then import a role as a JD. MySQL caches search results; the frontend also has a local cache, with force refresh to collect again.

Web collection requires local Microsoft Edge. Before first CLI use, run `python -m playwright install chromium` in the Python environment containing project dependencies. Platforms may require manual login or verification, and page / API changes can affect collection. Follow platform rules and use reasonable request rates.

### Independent CLI

From the repository root with backend dependencies installed:

```bash
python -m job_crawler login --platforms all
python -m job_crawler run --resume backend/data/samples/sample_resume.txt --keyword "Python 后端实习生" --city "广州" --platforms all --pages 1 --min-score 50 --top 50
```

Replace `python` with `backend\.venv\Scripts\python.exe` on Windows or `backend/.venv/bin/python` on macOS/Linux to reuse the prepared environment. Run `python -m job_crawler --help` for options.

The default output directory is `outputs/job_crawler/`, containing JSON, CSV, and Markdown, plus XLSX when `openpyxl` is available. CLI and web collection / ranking entry points are independent; their scores are not strictly equivalent.

### Optional browser extension

Load `browser-extension/` through Chrome/Edge's unpacked-extension option. Current `popup.js` and `manifest.json` default to **`localhost:8000`**, while the main backend uses **`9000`**. Align extension settings, default address, and host permission to `http://localhost:9000`, then reload. See the [extension README](browser-extension/README.en.md).

## Data and deployment

| Data | Location | Notes |
| --- | --- | --- |
| Resumes and JDs | MySQL `resumes`, `job_descriptions` | Original text and structured JSON |
| Analysis and reports | MySQL `analysis_tasks`, `match_reports` | Task state, dimension scores, report snapshots |
| Rewrites and question banks | MySQL `rewritten_resumes`, `interview_questions` | Generated content, user edits, question records |
| Job cache | MySQL `cached_job_searches` | Search conditions, results, errors |
| Browser login state | `.job_browser/`, `.job_crawler/`, relative to launch directory | Private runtime data; do not commit or share |
| Frontend temporary state | Browser localStorage / page memory | Some caches persist in-browser; page-supplied interview history is not a persistent conversation system |

The backend **requires MySQL and does not support SQLite**. Startup calls `Base.metadata.create_all()`, which creates missing tables but does not migrate existing schemas. Maintain MySQL backups and migrations separately; recloning code does not restore analysis history.

The project suits local or controlled single-instance deployment. There is no container setup, account system, or access isolation. The backend listens on all interfaces by default, so restrict network access. Real-model mode sends relevant resume, JD, and answer content to the configured service. Do not use unauthorized personal materials in public demonstrations.

Build the frontend with `npm run build`; outputs go to `frontend/dist/`. A static deployment needs SPA fallback and a `/api` reverse proxy to the backend. Vite's development proxy is not bundled into production assets.

## Common issues

| Symptom | First check |
| --- | --- |
| Backend startup / analysis fails | MySQL connection and permissions, Python 3.11 dependencies, explicit mock setting |
| Empty PDF parsing | Try a text PDF instead of scanned images |
| Frontend opens but API fails | Backend on 9000 and development proxy pointing there |
| Extension cannot connect | Align settings, default address, and host permission from 8000 to 9000 |
| Static frontend routes / APIs fail | Configure SPA fallback and `/api` proxy; Vite dev proxy is absent from dist |

## Development entry points

Full interfaces are in the running `/docs`. Resume upload, JD, analysis, and export are under `/api/v1`; the table below locates functionality.

## API overview

Except `/health`, paths below are relative to `/api/v1`. See the running [Swagger UI](http://localhost:9000/docs) for request and response schemas.

| Module | Representative endpoints | Function |
| --- | --- | --- |
| Resume | `POST /resumes/upload` · `POST /resumes/{id}/parse` | Upload and parse PDF |
| JD | `POST /jds` · `POST /jds/{id}/parse` | Create and parse a job description |
| Platform search | `POST /jds/platforms/search` | Search and rank roles |
| Analysis | `POST /analysis/run` · `GET /analysis/history/list` | Analyze and query history |
| Report | `GET /analysis/{id}/report` · `GET /analysis/{id}/export/word` | Retrieve report and export Word; PDF is also available |
| Rewrite | `POST /analysis/{id}/full-rewrite` · `PUT /analysis/{id}/full-rewrite` | Generate and save edits |
| Questions | `POST /analysis/{id}/interview-questions` · `POST /interview/score` | Generate questions and score an answer |
| Multi-turn interview | `POST /interview/start` · `/interview/chat` · `/interview/finish` | Start, follow up, and summarize |

## Development and verification

Run unit tests from the repository root with the backend virtual environment. Install `pytest` separately:

```bash
python -m pip install pytest==8.3.4
cd backend
python -m pytest
```

As in the CLI example, replace `python` with the appropriate virtual-environment interpreter or activate it first. Tests mainly cover scoring, skill normalization, rule-based JD parsing, diagnosis, and rewrite quality checks. See the [verification record](docs/validation.md) for publication scope.

Frontend type checking and production build:

```bash
cd frontend
npm ci
npm run build
```

When changing scoring, update weights in `scoring_service.py` and their tests together. Preserve evidence boundaries between original experience, role requirements, and generated content when changing rewrites.
