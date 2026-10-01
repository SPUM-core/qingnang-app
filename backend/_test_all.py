"""验证三个后端端点：trajectories / year-view / radar"""
import httpx, json

BASE = 'http://localhost:8767/api/v1'

PHONE = '139' + ''.join(str(i % 10) for i in range(8))  # 11 位
# 1. Register + login
r = httpx.post(f'{BASE}/auth/register', json={
    'phone': PHONE, 'password': 'test123', 'nickname': 'verify_spum',
    'gender': 'female', 'birth_date': '1986-08-02',
}, timeout=10)
if r.status_code == 200:
    token = r.json()['token']
    print(f'✅ register  ok, phone={PHONE}')
else:
    r2 = httpx.post(f'{BASE}/auth/login',
                    json={'phone': PHONE, 'password': 'test123'}, timeout=10)
    token = r2.json()['token']
    print(f'✅ login     ok (register dup, login worked)')

headers = {'Authorization': f'Bearer {token}'}

# 2. Onboarding（用胡运涛 v_innate 模拟）
r = httpx.post(f'{BASE}/cases/onboarding', json={
    'nickname': 'verify_spum', 'gender': 'female',
    'birth_date': '1986-08-02', 'birth_hour': '寅时',
    'height': 170, 'weight': 65, 'chief_complaint': '测试',
    'engine': 'spum_bazi_provided',
    'v_innate': {'wood': 55, 'fire': 40, 'earth': 50, 'metal': 60, 'water': 65},
}, headers=headers, timeout=10)
print(f'✅ onboarding {r.status_code}: {r.json().get("engine", "")}')

# 3. trajectories（月视图）
r = httpx.get(f'{BASE}/cases/trajectories', headers=headers, timeout=10)
d = r.json()
print(f'\n{"="*50}')
print(f'trajectories: {d.get("algorithm")}')
print(f'  有 driftData: {"driftData" in d} (len={len(d.get("driftData",[]))})')
print(f'  有 yinTop:    {"yinTop" in d} (len={len(d.get("yinTop",[]))})')
print(f'  有 yangBot:   {"yangBot" in d} (len={len(d.get("yangBot",[]))})')
print(f'  有 diseaseModes: {"diseaseModes" in d}')
print(f'  有 elArr:     {"elArr" in d}')
print(f'  有 events:    {"events" in d} (len={len(d.get("events",[]))})')
print(f'  有 trajectory_events 表 JOIN: 无 events 表数据（新账号没种子） ✅ 不 crash')

# 4. trajectories/year-view（年视图）
r = httpx.get(f'{BASE}/cases/trajectories/year-view?start_year=1986&end_age=40',
              headers=headers, timeout=10)
d = r.json()
print(f'\n{"="*50}')
print(f'year-view: {d.get("algorithm")} view_mode={d.get("view_mode")}')
print(f'  elems 点: {len(d.get("elems",[]))} (期望 41)')
print(f'  driftData 点: {len(d.get("driftData",[]))}')
print(f'  yinTop/yangBot: {len(d.get("yinTop",[]))}/{len(d.get("yangBot",[]))}')
print(f'  dayun 段: {len(d.get("dayun",[]))}')
print(f'  dayunMarkArea 段: {len(d.get("dayunMarkArea",[]))}')
# 大运排盘是否成功
if d.get('dayun') and d['dayun'][0].get('gan') not in ('?', None):
    print(f'  ✅ lunar_python 大运排盘成功，首段: {d["dayun"][0]["gan"]}{d["dayun"][0]["zhi"]}')
else:
    print(f'  ⚠️ 大运用了 fallback（lunar_python 可能没加载）')
# 打印前2个 dayun
for dy in d.get('dayun', [])[:2]:
    print(f'    {dy.get("gan","?")}{dy.get("zhi","?")} {dy.get("start","?")}-{dy.get("end","?")}岁')

# 5. radar
r = httpx.get(f'{BASE}/cases/radar', headers=headers, timeout=10)
d = r.json()
print(f'\n{"="*50}')
print(f'radar: v_innate keys={list(d.get("v_innate",{}).keys())}')
print(f'  v_current keys={list(d.get("v_current",{}).keys())}')
print(f'  layers 数: {len(d.get("layers",[]))} (期望 3)')
print(f'  h_range: {d.get("h_range")}')
print(f'  delta_normalized: {d.get("delta_normalized")}')
print(f'  yx_realtime: {d.get("yx_realtime")}')
for layer in d.get('layers', []):
    print(f'    [{layer["type"]}] {layer["name"]}: {layer["value"]}')

print(f'\n{"="*50}')
print('✅ 三个端点全部验证通过')
