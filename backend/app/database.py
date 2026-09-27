"""数据库引擎 + SessionLocal（PostgreSQL 为主，兼容 SQLite 仅用于本地调试）"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# SQLite 需要 check_same_thread=False；PostgreSQL 不需要额外 connect_args
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
    pool_pre_ping=True,  # PG 连接池自动探活
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()

def get_db():
    """FastAPI 依赖注入 - 每次请求一个 session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
