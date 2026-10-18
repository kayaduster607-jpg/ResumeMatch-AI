from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = True

    # ── CORS ───────────────────────────────────────────
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # ── Database ───────────────────────────────────────
    # 默认就是 MySQL；不要再回退 SQLite。
    # 你可以在 backend/.env 里覆盖成自己的 MySQL 地址。
    DATABASE_URL: str = "mysql+pymysql://root:password@127.0.0.1:3306/resume_match?charset=utf8mb4"

    # ── LLM / DeepSeek / OpenAI-compatible ─────────────
    # 支持：mock / openai / deepseek / openai_compatible
    LLM_PROVIDER: str = "deepseek"

    # OpenAI-compatible 通用配置；DeepSeek 也可以直接填这几个。
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"

    # DeepSeek 专用配置；当 LLM_PROVIDER=deepseek 时优先读取这里。
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 真实 LLM 模式下，分析/改写/面试如果调用失败，是否直接报错而不是降级成规则版。
    LLM_STRICT_MODE: bool = True


    # ── Browser / Edge crawler ─────────────────────────
    EDGE_PATH: str = ""
    EDGE_REMOTE_DEBUG_PORT: int = 9333
    # BOSS 更容易识别自动化导航；默认用 Edge 命令行把 BOSS URL 打到同一个托管浏览器，
    # 再由 CDP 读取页面/接口，减少 page.goto 触发空白页的概率。
    BOSS_OPEN_BY_EDGE_COMMAND: bool = True

    # ── Embedding ──────────────────────────────────────
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
