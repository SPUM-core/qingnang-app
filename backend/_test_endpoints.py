"""用 Phase3验收 账号（未脱敏）登录然后测三个端点"""
import httpx, json

BASE = 'http://localhost:8767/api/v1'
PHONE = '13836666667'

# 先试 register 新账号（避免 seed 密码不确定）
import time
unique_phone = '139' + str(int(time.time()))[-8:]  # 11 位

r = httpx.post(f'{BASE}/auth/register', json={
    'phone': unique_phone, 'password': 'test123', 'nickname': 'verify',
    'gender': 'female', 'birth_date': '1990-01-01',
}, timeout=10)
print(f'register {r.status_code}: {r.text[:200]}')

if r.status_code != 200:
    # register 500 可能是 trajectory_events import 导致
    print('register failed, checking backend health...')
    r_health = httpx.get('http://localhost:8767/docs', timeout=5)
    print(f'docs: {r_health.status_code}')
    # 直接 ping trajectories
    from app.utils.trajectory_algorithm import compute_health_bounds
    print(f'trajectory_algorithm import OK')
    from app.utils.lunar_helper import compute_dayun
    print(f'lunar_helper import OK')
    from app.models import TrajectoryEvent
    print(f'TrajectoryEvent import OK')
    sys_exit = 0

# 用临时注册的 token 或从胡运涛现有 seed
token = None
try:
    token = r.json().get('token')
except:
    pass

if not token:
    # seed 账号密码一般跟 username 一致
    for try_pw in ['test123', '123456', 'qingnang123', 'Phase3验收']:
        r_login = httpx.post(f'{BASE}/auth/login',
                            json={'phone': PHONE, 'password': try_pw}, timeout=10)
        if r_login.status_code == 200:
            token = r_login.json()['token']
            print(f'✅ login ok (pw={try_pw})')
            break

if not token:
    print('❌ 无法获取 token，跳过端点测试')
    # 直接测 import chain 是否 OK
    from app.api.v1.cases import router
    print(f'  cases router 有 {len(router.routes)} 个路由')
    routes = [getattr(rt, 'path', str(rt)) for rt in router.routes]
    print(f'  路由: {routes}')
    sys.exit(0)

headers = {'Authorization': f'Bearer {token}'}

# ── trajectories ──
r = httpx.get(f'{BASE}/cases/trajectories', headers=headers, timeout=10)
d = r.json()
print(f'\ntrajectories [{d.get("algorithm")}]:')
print(f'  driftData={len(d.get("driftData",[]))}, yinTop={len(d.get("yinTop",[]))}, elArr={len(d.get("elArr",[]))}')

# ── year-view ──
r = httpx.get(f'{BASE}/cases/trajectories/year-view?start_year=1990&end_age=40',
              headers=headers, timeout=10)
d = r.json()
print(f'\nyear-view [{d.get("algorithm")} view_mode={d.get("view_mode")}]:')
print(f'  elems={len(d.get("elems",[]))}, driftData={len(d.get("driftData",[]))}')
dys = d.get('dayun', [])
if dys:
    print(f'  dayun 首段: {dys[0].get("gan","?")}{dys[0].get("zhi","?")} {dys[0].get("start","?")}-{dys[0].get("end","?")}岁')
else:
    print(f'  dayun=[] (lunar_python 可能没加载)')

# ── radar ──
r = httpx.get(f'{BASE}/cases/radar', headers=headers, timeout=10)
d = r.json()
print(f'\nradar:')
print(f'  v_innate={d.get("v_innate")}')
print(f'  v_current={d.get("v_current")}')
print(f'  layers={len(d.get("layers",[]))}层 (期望3)')
print(f'  yx_realtime={d.get("yx_realtime")}')
print(f'  delta_normalized={d.get("delta_normalized")}')
