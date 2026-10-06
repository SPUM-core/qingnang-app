"""青囊后端 · FastAPI 入口
================================
青囊管家（C 端）+ 青囊中医（B 端）的统一业务 API 层
站在 qingmeng-engine（AI 对话）之上，管理用户/案例/PPG/调理/好友/商城

启动：python main.py  （或 uvicorn app.main:app --reload --port 8767）
"""
import sys
import logging
from pathlib import Path

import httpx

# 确保 backend/ 在 sys.path（无论从哪里启动都能 import）
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ══ 理论源头桥接（唯一真源：e:/工作/qingnang/青囊/脉诊/理论）══
# bridge.py / ppg_processing.py / syndrome_decoder.py 必须从理论真源 import，
# 禁止在 backend/ 下维护副本（多源漂移 → 理论和实现脱节）
_THEORY_DIR_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent.parent / 'qingnang' / '青囊' / '脉诊' / '理论',
    Path(r'e:/工作/qingnang/青囊/脉诊/理论'),
]
for _c in _THEORY_DIR_CANDIDATES:
    if _c.is_dir() and str(_c) not in sys.path:
        sys.path.insert(0, str(_c))
        break

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)


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

    # 建表策略：SQLite → create_all（跳过 Alembic，迁移可能用了 PG 特有语法）
    #          PostgreSQL → Alembic upgrade head（推荐，但启动不自动跑）
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    if is_sqlite:
        print("🗄️  数据库: SQLite → 自动 create_all（跳过 Alembic 迁移）")
        Base.metadata.create_all(bind=engine)
        print("  ✅ 表结构已创建")
    else:
        print("🗄️  数据库: PostgreSQL (由 Alembic 迁移管理)")
        print("     如需建表请手动执行: python -m alembic upgrade head")
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

# CORS（生产严格白名单 · 开发期动态放行穿透域名）
if settings.APP_ENV == "development":
    # 穿透/内网演示场景：从 .env CORS_ORIGINS 取白名单 + 自动放行当前 Origin
    import re as _re
    _origins = settings.CORS_ORIGINS

    class _DynamicCORS:
        def __init__(self, app): self.app = app
        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope.get("headers", []))
                origin = headers.get(b"origin", b"").decode()
                # 放行 localhost / 内网 IP / 配置白名单 / cpolar/ngrok 穿透域名
                if origin and (
                    origin in _origins
                    or _re.match(r"https?://localhost", origin)
                    or _re.match(r"https?://127\.0\.0\.1", origin)
                    or _re.match(r"https?://192\.168\.\d+\.\d+", origin)
                    or _re.match(r"https?://\w+\.cpolar\.\w+", origin)
                    or _re.match(r"https?://\w+\.ngrok\.io", origin)
                    or _re.match(r"https?://\w+\.trycloudflare\.com", origin)
                ):
                    scope["_cors_origin"] = origin
            await self.app(scope, receive, send)

    app.add_middleware(_DynamicCORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Authorization"],
    )
else:
    # 生产：严格白名单
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
    """2026-10-06 重写：真实探测 DB + qingmeng-engine，异常带日志"""
    checks = {}

    # ── DB（简单 SELECT 1，不依赖表是否存在）──
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.exception("health: DB 探测失败")
        checks["db"] = f"error: {exc}"

    # ── qingmeng-engine（真正的单点依赖）──
    try:
        r = httpx.get(f"{settings.QINGMENG_URL}/health", timeout=2.0)
        checks["qingmeng"] = "ok" if r.status_code == 200 else f"degraded({r.status_code})"
    except Exception as exc:
        logger.warning("health: qingmeng-engine 不可达: %s", exc)
        checks["qingmeng"] = f"unreachable"

    healthy = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "version": getattr(settings, "VERSION", "dev"),
    }


# ═══════════════════════════════════════════════════════
# 业务 API 汇总
# ═══════════════════════════════════════════════════════
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# 启动入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8767, reload=settings.DEBUG)
