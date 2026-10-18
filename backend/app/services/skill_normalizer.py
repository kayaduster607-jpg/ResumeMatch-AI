"""Skill normalization engine.

Normalizes raw skill strings to canonical names and categorizes them.
Supports alias lookup, fuzzy fallback, and deduplication.
"""

from app.schemas.skill import NormalizedSkill

# ── Category constants ─────────────────────────────────

CAT_PROGRAMMING = "programming_language"
CAT_FRONTEND = "frontend"
CAT_BACKEND = "backend"
CAT_DATABASE = "database"
CAT_AI_ML = "ai_ml"
CAT_DEVOPS = "devops"
CAT_TOOL = "tool"
CAT_SOFT = "soft_skill"
CAT_OTHER = "other"

# ── Skill dictionary ──────────────────────────────────
# Format: { alias_lower: (canonical_name, category, confidence) }

_SKILL_MAP: dict[str, tuple[str, str, float]] = {}

# Helper to register multiple aliases at once
def _reg(canonical: str, category: str, confidence: float, *aliases: str):
    for alias in aliases:
        _SKILL_MAP[alias.lower()] = (canonical, category, confidence)
    # Also register the canonical name itself
    _SKILL_MAP[canonical.lower()] = (canonical, category, confidence)


# ── Programming Languages ─────────────────────────────

_reg("Python",      CAT_PROGRAMMING, 0.99, "python", "py", "python3", "python2")
_reg("JavaScript",  CAT_PROGRAMMING, 0.99, "javascript", "js", "es6", "es2015", "ecmascript")
_reg("TypeScript",  CAT_PROGRAMMING, 0.99, "typescript", "ts")
_reg("Java",        CAT_PROGRAMMING, 0.99, "java")
_reg("Go",          CAT_PROGRAMMING, 0.99, "go", "golang")
_reg("C++",         CAT_PROGRAMMING, 0.99, "c++", "cpp", "c plus plus")
_reg("C",           CAT_PROGRAMMING, 0.95, "c")
_reg("C#",          CAT_PROGRAMMING, 0.99, "c#", "csharp", "c sharp")
_reg("Rust",        CAT_PROGRAMMING, 0.99, "rust")
_reg("PHP",         CAT_PROGRAMMING, 0.99, "php")
_reg("Ruby",        CAT_PROGRAMMING, 0.99, "ruby")
_reg("Swift",       CAT_PROGRAMMING, 0.99, "swift")
_reg("Kotlin",      CAT_PROGRAMMING, 0.99, "kotlin")
_reg("Scala",       CAT_PROGRAMMING, 0.99, "scala")
_reg("R",           CAT_PROGRAMMING, 0.90, "r")
_reg("MATLAB",      CAT_PROGRAMMING, 0.95, "matlab")
_reg("Shell",       CAT_PROGRAMMING, 0.95, "shell", "bash", "zsh")
_reg("SQL",         CAT_PROGRAMMING, 0.95, "sql")
_reg("Dart",        CAT_PROGRAMMING, 0.95, "dart")
_reg("Lua",         CAT_PROGRAMMING, 0.95, "lua")
_reg("Perl",        CAT_PROGRAMMING, 0.95, "perl")
_reg("Haskell",     CAT_PROGRAMMING, 0.95, "haskell")
_reg("Elixir",      CAT_PROGRAMMING, 0.95, "elixir")
_reg("Clojure",     CAT_PROGRAMMING, 0.95, "clojure")
_reg("Objective-C", CAT_PROGRAMMING, 0.95, "objective-c", "objectivec", "oc")

# ── Frontend ──────────────────────────────────────────

_reg("React",           CAT_FRONTEND, 0.99, "react", "reactjs", "react.js", "react js")
_reg("Vue",             CAT_FRONTEND, 0.99, "vue", "vuejs", "vue.js", "vue js", "vuejs3", "vue3")
_reg("Angular",         CAT_FRONTEND, 0.99, "angular", "angularjs", "angular.js", "angular2")
_reg("Next.js",         CAT_FRONTEND, 0.99, "next.js", "nextjs", "next", "next js")
_reg("Nuxt.js",         CAT_FRONTEND, 0.99, "nuxt.js", "nuxtjs", "nuxt", "nuxt js")
_reg("Svelte",          CAT_FRONTEND, 0.95, "svelte", "sveltejs", "svelte.js")
_reg("HTML",            CAT_FRONTEND, 0.95, "html", "html5")
_reg("CSS",             CAT_FRONTEND, 0.95, "css", "css3")
_reg("Sass",            CAT_FRONTEND, 0.95, "sass", "scss")
_reg("Less",            CAT_FRONTEND, 0.95, "less")
_reg("Tailwind CSS",    CAT_FRONTEND, 0.99, "tailwind css", "tailwindcss", "tailwind")
_reg("Bootstrap",       CAT_FRONTEND, 0.95, "bootstrap")
_reg("Material-UI",     CAT_FRONTEND, 0.95, "material-ui", "mui", "material ui")
_reg("Ant Design",      CAT_FRONTEND, 0.95, "ant design", "antd", "ant-design")
_reg("Element UI",      CAT_FRONTEND, 0.95, "element ui", "element-ui", "element plus")
_reg("Webpack",         CAT_FRONTEND, 0.95, "webpack")
_reg("Vite",            CAT_FRONTEND, 0.95, "vite")
_reg("jQuery",          CAT_FRONTEND, 0.90, "jquery")
_reg("Redux",           CAT_FRONTEND, 0.95, "redux")
_reg("Vuex",            CAT_FRONTEND, 0.95, "vuex", "pinia")
_reg("Three.js",        CAT_FRONTEND, 0.95, "three.js", "threejs", "three")
_reg("ECharts",         CAT_FRONTEND, 0.95, "echarts", "e-charts")
_reg("D3.js",           CAT_FRONTEND, 0.95, "d3.js", "d3js", "d3")

# ── Backend ───────────────────────────────────────────

_reg("Node.js",         CAT_BACKEND, 0.99, "node.js", "nodejs", "node", "node js")
_reg("Express",         CAT_BACKEND, 0.95, "express", "expressjs", "express.js", "express js")
_reg("FastAPI",         CAT_BACKEND, 0.99, "fastapi", "fast api", "fast-api")
_reg("Django",          CAT_BACKEND, 0.99, "django")
_reg("Flask",           CAT_BACKEND, 0.99, "flask")
_reg("Spring Boot",     CAT_BACKEND, 0.99, "spring boot", "springboot", "spring-boot")
_reg("Spring",          CAT_BACKEND, 0.95, "spring", "spring framework")
_reg("Gin",             CAT_BACKEND, 0.95, "gin", "gin-gonic")
_reg("Laravel",         CAT_BACKEND, 0.95, "laravel")
_reg("Rails",           CAT_BACKEND, 0.95, "rails", "ruby on rails", "ror")
_reg("NestJS",          CAT_BACKEND, 0.95, "nestjs", "nest.js", "nest js")
_reg("Tornado",         CAT_BACKEND, 0.90, "tornado")
_reg("Sanic",           CAT_BACKEND, 0.90, "sanic")
_reg("gRPC",            CAT_BACKEND, 0.95, "grpc", "g rpc")
_reg("GraphQL",         CAT_BACKEND, 0.95, "graphql", "graph ql", "graph ql")
_reg("RESTful",         CAT_BACKEND, 0.90, "restful", "rest", "rest api", "restful api")
_reg("Thrift",          CAT_BACKEND, 0.90, "thrift")
_reg("Celery",          CAT_BACKEND, 0.90, "celery")
_reg("Tornado",         CAT_BACKEND, 0.90, "tornado")

# ── Database ──────────────────────────────────────────

_reg("MySQL",           CAT_DATABASE, 0.99, "mysql")
_reg("PostgreSQL",      CAT_DATABASE, 0.99, "postgresql", "postgres", "pg")
_reg("MongoDB",         CAT_DATABASE, 0.99, "mongodb", "mongo")
_reg("Redis",           CAT_DATABASE, 0.99, "redis")
_reg("SQLite",          CAT_DATABASE, 0.95, "sqlite")
_reg("Oracle",          CAT_DATABASE, 0.95, "oracle", "oracle db")
_reg("SQL Server",      CAT_DATABASE, 0.95, "sql server", "sqlserver", "mssql", "ms sql")
_reg("Elasticsearch",   CAT_DATABASE, 0.95, "elasticsearch", "elastic", "es", "elastic search")
_reg("ClickHouse",      CAT_DATABASE, 0.95, "clickhouse", "click house")
_reg("TiDB",            CAT_DATABASE, 0.95, "tidb")
_reg("Cassandra",       CAT_DATABASE, 0.95, "cassandra")
_reg("DynamoDB",        CAT_DATABASE, 0.95, "dynamodb", "dynamo db", "dynamo")
_reg("Neo4j",           CAT_DATABASE, 0.95, "neo4j", "neo 4j")
_reg("HBase",           CAT_DATABASE, 0.95, "hbase")
_reg("InfluxDB",        CAT_DATABASE, 0.90, "influxdb", "influx db", "influx")
_reg("CouchDB",         CAT_DATABASE, 0.90, "couchdb", "couch db")
_reg("Memcached",       CAT_DATABASE, 0.90, "memcached", "memcache")

# ── AI / ML ───────────────────────────────────────────

_reg("PyTorch",             CAT_AI_ML, 0.99, "pytorch", "py torch", "py-torch")
_reg("TensorFlow",          CAT_AI_ML, 0.99, "tensorflow", "tf", "tensor flow")
_reg("Keras",               CAT_AI_ML, 0.95, "keras")
_reg("scikit-learn",        CAT_AI_ML, 0.95, "scikit-learn", "sklearn", "scikit learn")
_reg("Pandas",              CAT_AI_ML, 0.95, "pandas", "pd")
_reg("NumPy",               CAT_AI_ML, 0.95, "numpy", "np")
_reg("Matplotlib",          CAT_AI_ML, 0.90, "matplotlib")
_reg("OpenCV",              CAT_AI_ML, 0.95, "opencv", "cv2")
_reg("Hugging Face",        CAT_AI_ML, 0.95, "hugging face", "huggingface", "hf", "transformers")
_reg("LangChain",           CAT_AI_ML, 0.95, "langchain", "lang chain", "lang-chain")
_reg("LlamaIndex",          CAT_AI_ML, 0.95, "llamaindex", "llama index", "llama-index")
_reg("OpenAI",              CAT_AI_ML, 0.90, "openai", "open ai", "gpt", "chatgpt", "gpt-4", "gpt-3.5")
_reg("LLM",                 CAT_AI_ML, 0.90, "llm", "large language model", "大模型", "大语言模型")
_reg("RAG",                 CAT_AI_ML, 0.90, "rag", "retrieval augmented generation", "检索增强生成")
_reg("NLP",                 CAT_AI_ML, 0.90, "nlp", "natural language processing", "自然语言处理")
_reg("Computer Vision",     CAT_AI_ML, 0.90, "computer vision", "cv", "计算机视觉")
_reg("Deep Learning",       CAT_AI_ML, 0.90, "deep learning", "dl", "深度学习")
_reg("Machine Learning",    CAT_AI_ML, 0.90, "machine learning", "ml", "机器学习")
_reg("Embedding",           CAT_AI_ML, 0.85, "embedding", "vector embedding", "向量化")
_reg("Fine-tuning",         CAT_AI_ML, 0.90, "fine-tuning", "finetuning", "fine tuning", "微调")
_reg("Prompt Engineering",  CAT_AI_ML, 0.90, "prompt engineering", "prompt engineering", "提示工程")

# Vector databases
_reg("Chroma",              CAT_AI_ML, 0.90, "chroma", "chromadb", "chroma db")
_reg("FAISS",               CAT_AI_ML, 0.90, "faiss", "facebook ai similarity search")
_reg("Pinecone",            CAT_AI_ML, 0.90, "pinecone")
_reg("Weaviate",            CAT_AI_ML, 0.90, "weaviate")
_reg("Milvus",              CAT_AI_ML, 0.90, "milvus")
_reg("Qdrant",              CAT_AI_ML, 0.90, "qdrant")
_reg("向量数据库",           CAT_AI_ML, 0.85, "向量数据库", "vector database", "vector db")

# ── DevOps ────────────────────────────────────────────

_reg("Docker",          CAT_DEVOPS, 0.99, "docker")
_reg("Kubernetes",      CAT_DEVOPS, 0.99, "kubernetes", "k8s", "kube")
_reg("Nginx",           CAT_DEVOPS, 0.95, "nginx")
_reg("Apache",          CAT_DEVOPS, 0.90, "apache", "apache httpd")
_reg("Linux",           CAT_DEVOPS, 0.95, "linux", "centos", "ubuntu", "debian")
_reg("AWS",             CAT_DEVOPS, 0.95, "aws", "amazon web services")
_reg("GCP",             CAT_DEVOPS, 0.95, "gcp", "google cloud", "google cloud platform")
_reg("Azure",           CAT_DEVOPS, 0.95, "azure", "microsoft azure")
_reg("Terraform",       CAT_DEVOPS, 0.95, "terraform")
_reg("Ansible",         CAT_DEVOPS, 0.90, "ansible")
_reg("Jenkins",         CAT_DEVOPS, 0.90, "jenkins")
_reg("GitHub Actions",  CAT_DEVOPS, 0.90, "github actions", "gh actions")
_reg("GitLab CI",       CAT_DEVOPS, 0.90, "gitlab ci", "gitlab-ci")
_reg("CI/CD",           CAT_DEVOPS, 0.90, "ci/cd", "cicd", "ci cd")
_reg("Prometheus",      CAT_DEVOPS, 0.90, "prometheus")
_reg("Grafana",         CAT_DEVOPS, 0.90, "grafana")
_reg("Istio",           CAT_DEVOPS, 0.90, "istio")

# ── Tools ─────────────────────────────────────────────

_reg("Git",             CAT_TOOL, 0.95, "git")
_reg("GitHub",          CAT_TOOL, 0.95, "github")
_reg("GitLab",          CAT_TOOL, 0.95, "gitlab")
_reg("Bitbucket",       CAT_TOOL, 0.90, "bitbucket")
_reg("Jira",            CAT_TOOL, 0.90, "jira")
_reg("Confluence",      CAT_TOOL, 0.90, "confluence")
_reg("VS Code",         CAT_TOOL, 0.90, "vs code", "vscode", "visual studio code")
_reg("IntelliJ",        CAT_TOOL, 0.90, "intellij", "intellij idea")
_reg("PyCharm",         CAT_TOOL, 0.90, "pycharm")
_reg("Postman",         CAT_TOOL, 0.90, "postman")
_reg("Swagger",         CAT_TOOL, 0.90, "swagger", "openapi")
_reg("Kafka",           CAT_TOOL, 0.95, "kafka", "apache kafka")
_reg("RabbitMQ",        CAT_TOOL, 0.95, "rabbitmq", "rabbit mq", "rabbit-mq")
_reg("MQTT",            CAT_TOOL, 0.90, "mqtt")
_reg("Figma",           CAT_TOOL, 0.85, "figma")
_reg("Notion",          CAT_TOOL, 0.80, "notion")

# ── Soft Skills ───────────────────────────────────────

_reg("沟通能力",     CAT_SOFT, 0.85, "沟通能力", "沟通", "communication", "communication skills")
_reg("团队协作",     CAT_SOFT, 0.85, "团队协作", "团队合作", "teamwork", "team collaboration")
_reg("学习能力",     CAT_SOFT, 0.85, "学习能力", "快速学习", "learning ability", "fast learner")
_reg("解决问题",     CAT_SOFT, 0.85, "解决问题", "problem solving", "problem-solving", "问题解决能力")
_reg("领导力",       CAT_SOFT, 0.80, "领导力", "leadership", "团队管理")
_reg("时间管理",     CAT_SOFT, 0.80, "时间管理", "time management")
_reg("自驱力",       CAT_SOFT, 0.80, "自驱力", "主动", "self-motivated", "self-driven")
_reg("抗压能力",     CAT_SOFT, 0.80, "抗压能力", "抗压", "压力", "resilience")


# ── Public API ─────────────────────────────────────────

def normalize_skill(skill: str) -> NormalizedSkill:
    """Normalize a single skill string.

    Returns a NormalizedSkill with the canonical name, category, and confidence.
    Falls back to title-cased original if no match is found.
    """
    key = skill.strip().lower()
    if not key:
        return NormalizedSkill(raw=skill, name=skill, category=CAT_OTHER, confidence=0.0)

    # Exact match
    if key in _SKILL_MAP:
        name, category, confidence = _SKILL_MAP[key]
        return NormalizedSkill(raw=skill, name=name, category=category, confidence=confidence)

    # Substring match: try to find a known skill inside the input
    for alias, (name, category, confidence) in _SKILL_MAP.items():
        if alias in key or key in alias:
            return NormalizedSkill(
                raw=skill, name=name, category=category,
                confidence=max(0.0, confidence - 0.1),  # lower confidence for fuzzy
            )

    # No match: return as-is with "other" category
    return NormalizedSkill(
        raw=skill,
        name=skill.strip().title(),
        category=CAT_OTHER,
        confidence=0.3,
    )


def normalize_skills(skills: list[str]) -> list[NormalizedSkill]:
    """Normalize a list of skills, deduplicating by canonical name.

    When duplicates exist, the one with higher confidence is kept.
    """
    seen: dict[str, NormalizedSkill] = {}

    for skill in skills:
        if not skill or not skill.strip():
            continue
        normalized = normalize_skill(skill)
        key = normalized.name.lower()
        if key not in seen or normalized.confidence > seen[key].confidence:
            seen[key] = normalized

    return list(seen.values())
