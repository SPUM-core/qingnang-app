"""查 qingmeng-engine bazi 端点返回结构（特别是 dayun）"""
import httpx, json

r = httpx.post('http://localhost:8000/v1/reasoning/bazi', json={
    'birth_date': '1986-08-02',
    'birth_hour': '03',
    'birthplace': 'Hangzhou',
}, timeout=15.0)
print('status:', r.status_code)
d = r.json()
print('top keys:', list(d.keys()))
print()
# 找所有 dayun/da_yun/daYun/大运 相关
for k, v in d.items():
    kl = k.lower()
    if 'dayun' in kl or 'da_yun' in kl or 'dayun' in kl or 'yung' in kl or 'liunian' in kl:
        print(f'FOUND [{k}]: {json.dumps(v, ensure_ascii=False)[:800]}')
print()
# 完整输出（先看）
for k in ['v_innate', 'bazi', 'pillars', 'engine', 'dayun', 'da_yun', 'daYun', 'da_yun_pillars', 'lunar']:
    if k in d:
        print(f'[{k}]: {json.dumps(d[k], ensure_ascii=False)[:800]}')
print()
print('--- full response ---')
print(json.dumps(d, ensure_ascii=False, indent=2)[:2500])
