import httpx, json

payload = {
    'user_id': 'test_final_v2',
    'v_obs': {'wood': 60.5, 'fire': 43.1, 'earth': 59.0, 'metal': 58.5, 'water': 20.0},
    'sqi': 0.612,
    'delta_f': {'wood': 0.211, 'fire': -0.138, 'earth': 0.181, 'metal': 0.169, 'water': -0.6},
    'syndrome_hint': 'bridge: 心脉瘀阻（置信度42%）; 上热下寒; 硬度跨视角不一致(一致性0.21)',
    'evolve_frames': 3,
}
r = httpx.post('http://localhost:8000/v1/reasoning/ppg', json=payload, timeout=60)
resp = r.json()
print(f'HTTP {r.status_code}')
lp = resp.get('llm_provider')
lm = resp.get('llm_ms')
print(f'llm_provider: {lp}  llm_ms: {lm}ms')
print()
print('=== 确定性拓扑层 summary ===')
print(resp.get('summary'))
print()
print('=== LLM 增强解读 ===')
li = resp.get('llm_interpretation')
print(li if li else '(无 LLM 增强)')
