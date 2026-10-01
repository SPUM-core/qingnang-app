"""胡运涛账号重置到病历真实数据"""
import os, sys, json, glob
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
sys.path.insert(0, 'e:/工作/qingnang-APP/backend')

from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL)

# ── 引擎八字推演的真实结果（唯一真源） ──
BAZI = "丁卯/己酉/甲子/丙寅"
V_INNATE_TRUE = {'wood': 34, 'fire': 31, 'earth': 15, 'metal': 10, 'water': 10}
GANZHI = {
    'year': '丁卯',
    'month': '己酉',
    'day': '甲子',
    'hour': '丙寅',
}

# ── 病历 S_effective（当前健康态）── 转 0-100 ──
# 木: ↓活性 + ↓↓内容 → 40
# 火: 基线↓↓↓ + 虚浮↑ → 50（虚性偏高）
# 土: ↓↓↓ → 25
# 金: ↓↓ → 35
# 水: ↓↓↓ → 25
V_BASELINE_CURRENT = {'wood': 40, 'fire': 50, 'earth': 25, 'metal': 35, 'water': 25}

QINGNANG_ID = 'QN-SPUM-CASE-002'
USER_ID = 8

# 引擎拓扑持久化路径
TOPO_DIR = os.path.expanduser('~/.qingmeng/user_states')

with engine.connect() as conn:
    trans = conn.begin()
    try:
        # Step 1: 重置 users.v_base（当前健康基线）
        conn.execute(text("""
            UPDATE users SET
                v_base = :vb,
                updated_at = NOW()
            WHERE qingnang_id = :qid
        """), {'vb': json.dumps(V_BASELINE_CURRENT), 'qid': QINGNANG_ID})
        print(f"✅ users.v_base = {V_BASELINE_CURRENT}")

        # Step 2: 重置 cases
        conn.execute(text("""
            UPDATE cases SET
                bazi = :bazi,
                ganzhi_year = :gy,
                ganzhi_month = :gm,
                ganzhi_day = :gd,
                v_innate = :vi,
                v_baseline = :vb,
                v_current = NULL,
                updated_at = NOW()
            WHERE user_id = :uid
        """), {
            'bazi': BAZI,
            'gy': GANZHI['year'],
            'gm': GANZHI['month'],
            'gd': GANZHI['day'],
            'vi': json.dumps(V_INNATE_TRUE),
            'vb': json.dumps(V_BASELINE_CURRENT),
            'uid': USER_ID,
        })
        print(f"✅ cases.bazi = {BAZI}")
        print(f"✅ cases.ganzhi = {GANZHI}")
        print(f"✅ cases.v_innate = {V_INNATE_TRUE}")
        print(f"✅ cases.v_baseline = {V_BASELINE_CURRENT}")
        print(f"✅ cases.v_current = NULL")

        # Step 3: 删除引擎拓扑文件
        os.makedirs(TOPO_DIR, exist_ok=True)
        for f in glob.glob(os.path.join(TOPO_DIR, f'user_*{QINGNANG_ID}*.pkl')):
            os.remove(f)
            print(f"🗑️  删除引擎拓扑: {f}")
        # 也删可能的 user_id 数字命名
        for f in glob.glob(os.path.join(TOPO_DIR, f'user_{USER_ID}.pkl')):
            os.remove(f)
            print(f"🗑️  删除引擎拓扑: {f}")

        trans.commit()
        print("\n✅ 数据库重置完成！")

        # ── 验证 ──
        r = conn.execute(text(
            "SELECT qingnang_id, v_base FROM users WHERE id = :uid"
        ), {'uid': USER_ID})
        for row in r.fetchall():
            print(f"\n验证 user: {row[0]}, v_base={row[1]}")
        
        r2 = conn.execute(text(
            "SELECT bazi, ganzhi_year, ganzhi_month, ganzhi_day, "
            "v_innate, v_baseline FROM cases WHERE user_id = :uid"
        ), {'uid': USER_ID})
        for row in r2.fetchall():
            print(f"验证 case: bazi={row[0]}")
            print(f"  ganzhi={row[1]}/{row[2]}/{row[3]}")
            print(f"  v_innate={row[4]}")
            print(f"  v_baseline={row[5]}")

    except Exception as e:
        trans.rollback()
        print(f"❌ 失败: {e}")
        raise
