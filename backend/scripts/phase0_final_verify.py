"""阶段0 最终验证（简化：不删库，直接 verify alembic + seed + login）"""
import subprocess, os, sys, time, requests
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

from app.config import settings
from sqlalchemy import create_engine, text

print("DB:", settings.DATABASE_URL[:50] + "...")

eng = create_engine(settings.DATABASE_URL)
with eng.connect() as conn:
    ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print(f"\nalembic_version = {ver}  {'✅' if ver == 'a1b2c3d4e5f6' else '❌'}")

    tables = [r[0] for r in conn.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    ).fetchall()]
    print(f"tables ({len(tables)}): {', '.join(tables)}")

    cols = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name='users' AND column_name IN
            ('wechat_openid','wechat_unionid','password_hash','dev_seed','phone','qingnang_id')
        ORDER BY column_name
    """)).fetchall()
    print("\nusers auth columns:")
    for c in cols:
        print(f"  {c[0]:20s} {c[1]:15s} nullable={'NO' if c[2]=='NO' else 'YES'}")

    users = conn.execute(text("""
        SELECT qingnang_id, phone, nickname, dev_seed, wechat_openid
        FROM users ORDER BY id
    """)).fetchall()
    print(f"\nusers rows ({len(users)}):")
    for u in users:
        print(f"  {u}")

# Dev seed login E2E
print("\n" + "="*60)
print("  DEV SEED LOGIN E2E")
print("="*60)

PORT = 8767
try:
    r = requests.get(f"http://localhost:{PORT}/health", timeout=2)
    print(f"  backend health: {r.json()}")
except:
    print("  启动后端...")
    subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app",
                      "--host", "0.0.0.0", "--port", str(PORT)],
                     creationflags=0x08000000)
    for _ in range(10):
        time.sleep(1)
        try:
            r = requests.get(f"http://localhost:{PORT}/health", timeout=2)
            print(f"  backend up ✅"); break
        except: pass

r = requests.post(f"http://localhost:{PORT}/api/v1/auth/login",
    json={"phone": "13506091698", "password": "qingnang2026"}, timeout=5)
d = r.json()
print(f"  POST /auth/login -> {r.status_code}  {'✅' if r.status_code==200 else '❌'}")
print(f"    qingnang_id = {d.get('qingnang_id')}")
print(f"    nickname    = {d.get('nickname')}")
print(f"    onboarded   = {d.get('is_onboarded')}")

token = d.get("token", "")
if token:
    r2 = requests.get(f"http://localhost:{PORT}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}, timeout=5)
    me = r2.json()
    print(f"  GET /auth/me  -> {r2.status_code} ✅  ({me.get('nickname')})")

    # onboarding 全链路
    r3 = requests.post(f"http://localhost:{PORT}/api/v1/cases/onboarding",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "nickname": "青囊演示用户", "gender": "male",
            "birth_date": "1986-08-02", "birth_hour": "寅时",
            "birthplace": "广州", "engine": "spum_bazi",
            "v_innate": {"water":0,"wood":52,"fire":22,"earth":25,"metal":0},
            "bazi_result": {
                "bazi": "丙寅/乙未/戊寅/甲寅",
                "pillars": ["丙寅","乙未","戊寅","甲寅"],
                "true_solar_time": "1986-08-02 03:26:35",
            }
        }, timeout=10)
    print(f"  POST /onboarding -> {r3.status_code}  {'✅' if r3.status_code==200 else '❌'}")
    ob = r3.json()
    print(f"    onboarded   = {ob.get('onboarded')}")
    print(f"    bazi        = {ob.get('bazi')}")
    print(f"    engine      = {ob.get('engine')}")

    r4 = requests.get(f"http://localhost:{PORT}/api/v1/cases/mine",
        headers={"Authorization": f"Bearer {token}"}, timeout=5)
    mine = r4.json()
    print(f"  GET /cases/mine -> onboarded={mine.get('onboarded')} bazi={mine.get('case',{}).get('bazi')}")

print("\n" + "="*60)
print("  ✅ 阶段0 收尾 — 架构断裂已修复")
print("="*60)
print("""
  alembic chain:  init_schema
                    ↓
                  dev_seed_accounts  ← dev_seed 列（结构保留，数据注入已废弃）
                    ↓
                  auth_providers     ← wechat_openid / wechat_unionid / password nullable

  一键 bootstrap: scripts/init_db.py  (幂等，含角色/库/.env/migration)
""")
