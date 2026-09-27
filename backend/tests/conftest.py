"""pytest 配置 + 核心 fixture"""
import os
import sys
import tempfile
import pytest
from pathlib import Path

# ── 1. 设置测试环境变量（必须在 import app 之前）─
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 用临时文件 SQLite（:memory: 在多个 connection 间不共享）
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["SECRET_KEY"] = "test-insecure-secret-key-for-pytest-32chars!!"
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = '["http://localhost:5173"]'
os.environ["QINGMENG_URL"] = "http://localhost:1"


# ── 2. 提前 import（用 env 覆盖后的配置）─
from app import models                    # noqa: F401 — 注册模型
from app import database                  # 绑定到 env 指定的 SQLite 文件
from app.database import Base, engine
from app.main import app                  # 触发整个 app 初始化


# ── 3. 在实际 engine 上建表（Alembic 不在 SQLite 上跑）─
Base.metadata.create_all(engine)


@pytest.fixture
def client():
    """FastAPI TestClient — 每个 fixture 从同一个 DB 文件读取"""
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    """注册 + 登录后的 Authorization header"""
    import random
    phone = f"139{random.randint(10000000, 99999999)}"
    r = client.post("/api/v1/auth/register", json={
        "phone": phone, "password": "test2026", "nickname": "pytest测试"
    })
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:300]}"
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def onboarded_user(client, auth_headers):
    """完成 onboarding 的用户（返回 headers）"""
    r = client.post("/api/v1/cases/onboarding", json={
        "nickname": "pytest测试", "gender": "male",
        "birth_date": "1992-03-15", "birth_hour": "午时",
        "birthplace": "上海", "engine": "spum_bazi",
        "v_innate": {"wood": 55, "fire": 30, "earth": 60, "metal": 45, "water": 50},
        "bazi_result": {"bazi": "壬申/癸卯/庚寅/壬午",
                        "pillars": ["壬申","癸卯","庚寅","壬午"],
                        "true_solar_time": "1992-03-15 11:52:00"},
    }, headers=auth_headers)
    assert r.status_code == 200, f"onboarding failed: {r.status_code} {r.text[:200]}"
    return auth_headers


# ── 会话级清理 ──
def pytest_sessionfinish():
    import os as _os
    try:
        _os.unlink(_tmp_db.name)
    except OSError:
        pass
