"""青囊后端 · FastAPI 入口
================================
青囊管家（C 端）+ 青囊中医（B 端）的统一业务 API 层
站在 qingmeng-engine（AI 对话）之上，管理用户/案例/PPG/调理/好友/商城

启动：python main.py  （或 uvicorn app.main:app --reload --port 8767）
"""
import sys
from pathlib import Path

# 确保 backend/ 在 sys.path（无论从哪里启动都能 import）
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.api.v1.router import api_router


def func_now_sql():
    """启动自检用：执行一条无副作用的 SQL"""
    return text("SELECT 1")


# ═══════════════════════════════════════════════════════
# 生命周期 - 启动时创建表 + 种子数据注入
# ═══════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n{'='*60}")
    print(f"🌿 {settings.APP_NAME}  v{settings.VERSION}")
    print(f"{'='*60}")

    # 阶段0：表结构由 Alembic 迁移管理（python -m alembic upgrade head）
    print("🗄️  数据库: PostgreSQL (由 Alembic 迁移管理)")
    try:
        with engine.connect() as conn:
            conn.execute(func_now_sql())
        print("  ✅ 数据库连接正常")
    except Exception as exc:
        print(f"  ⚠️ 数据库连接失败: {exc}")
        print("     请先执行: python -m alembic upgrade head")

    # 种子数据（默认关闭，避免注入假数据）
    if settings.AUTO_SEED:
        from seed.seed_data import run_seed
        db = SessionLocal()
        try:
            run_seed(db)
        finally:
            db.close()

    print(f"\n🚀 启动完成！")
    print(f"   业务 API:  http://localhost:8767{settings.API_V1_PREFIX}")
    print(f"   Docs:      http://localhost:8767/docs")
    print(f"   ReDoc:     http://localhost:8767/redoc")
    print(f"   数据库:    {settings.DATABASE_URL.split('@')[-1]}")
    print(f"   青檬引擎:  {settings.QINGMENG_URL}")
    print(f"{'='*60}\n")

    yield

    print("\n🛑 青囊后端已停止")


# ═══════════════════════════════════════════════════════
# FastAPI 应用
# ═══════════════════════════════════════════════════════
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="青囊管家 + 青囊中医 · SPUM 业务 API 层",
    lifespan=lifespan,
)

# CORS（域名白名单，来源 settings.CORS_ORIGINS；禁止通配符 + 凭据组合）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════
# 安全响应头中间件
# ═══════════════════════════════════════════════════════
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    # 禁止浏览器 MIME 类型猜测（防 MIME 嗅探攻击）
    response.headers["X-Content-Type-Options"] = "nosniff"
    # 禁止 iframe 嵌入（防点击劫持）
    response.headers["X-Frame-Options"] = "DENY"
    # 严格 HTTPS 传输（生产环境 1 年 + includeSubDomains）
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # 内容安全策略 — 仅允许同源 + 必要的 CDN/字体
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' http://localhost:5173 http://127.0.0.1:5173; "
        "frame-ancestors 'none'"
    )
    # 禁止访问者地理位置等敏感 API（可选宽松）
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # 引用策略
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ═══════════════════════════════════════════════════════
# 根路由 + 健康检查
# ═══════════════════════════════════════════════════════
@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "api_prefix": settings.API_V1_PREFIX,
        "endpoints": [
            "/auth/register", "/auth/login", "/auth/me",
            "/cases/mine", "/cases/onboarding",
            "/ppg/upload", "/ppg/history",
            "/treatment/versions", "/treatment/current",
            "/friends/list", "/friends/add", "/friends/match/{id}",
            "/assistant/chat", "/assistant/health",
            "/shop/items", "/shop/items/{sku}", "/shop/recommend",
            "/challenges/mine",
            "/notifications/today",
            "/doctor/my-patients", "/doctor/patients/{id}",
        ],
    }


@app.get("/health")
def health():
    """整体健康检查"""
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(Base.metadata.tables.get("users", None).select().limit(1)
                         if "users" in Base.metadata.tables else None)
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "version": settings.VERSION,
    }


# ═══════════════════════════════════════════════════════
# 业务 API 汇总
# ═══════════════════════════════════════════════════════
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# 启动入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8767, reload=settings.DEBUG)
