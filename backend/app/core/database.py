from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

if settings.DATABASE_URL.startswith("sqlite"):
    raise RuntimeError(
        "当前版本要求使用 MySQL，不再使用 SQLite。请在 backend/.env 设置："
        "DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/resume_match?charset=utf8mb4"
    )

engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
    "pool_recycle": 3600,
    "pool_size": 5,
    "max_overflow": 10,
    "future": True,
}

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables for MySQL development use."""
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
