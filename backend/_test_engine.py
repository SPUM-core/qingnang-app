"""测试脚本：用 bridge 结果调 qingmeng-engine PPG 端点（Ollama vs DeepSeek 对比）"""
import httpx, json, time

# bridge 分析结果（同一份 CheezPPG filtered 原始波形）
bridge_df = {'wood': 0.211, 'fire': -0.138, 'earth': 0.181, 'metal': 0.169, 'water': -0.600}
bridge_vobs = {k: round(50 + 50*v, 1) for k, v in bridge_df.items()}
bridge_sqi = 0.612

payload = {
    'user_id': 'test_llm_compare_001',
    'v_obs': bridge_vobs,
    'sqi': bridge_sqi,
    'delta_f': bridge_df,
    'syndrome_hint': 'bridge: 心脉瘀阻（置信度42%）; 上热下寒; 硬度跨视角不一致(一致性0.21)',
    'evolve_frames': 3,
}

print('=== Payload (bridge 分析结果) ===')
print(f'v_obs: {bridge_vobs}')
print(f'delta_f: {bridge_df}')
print(f'SQI: {bridge_sqi}')
print()

# 测 qingmeng-engine（当前是 DeepSeek 模式）
t0 = time.time()
try:
    r = httpx.post('http://localhost:8000/v1/reasoning/ppg', json=payload, timeout=30)
    dt = time.time() - t0
    print(f'=== qingmeng-engine (DeepSeek mode) ===')
    print(f'HTTP {r.status_code} | 用时 {dt:.1f}s')
    resp = r.json()
    print()
    print(f'S_graph (拓扑层): {resp.get("S_graph")}')
    print(f'pathologies (病理标签): {resp.get("pathologies")}')
    print(f'summary: {resp.get("summary", "(无)")}')
    ts = resp.get('topology_status', {})
    if ts:
        print(f'topology_status: {json.dumps(ts, ensure_ascii=False)[:200]}')
except Exception as e:
    print(f'引擎调用失败: {e}')

# 直接测 DeepSeek API（不用引擎包装）
print()
print('=== DeepSeek 直接调用 (同一份 bridge 结果 + SPUM 系统提示) ===')
DEEPSEEK_KEY = 'sk-9bae9eefa43346e88f26516bc23f1ec5'
system = """你是 SPUM（关系网络本体论）的推理助手。回答须守住四条底线：
① 关系先于实体——不把任何对象当作先于关系的独立实体；
② 拓扑先于几何——五形是同一批节点的5种相位，不是5个独立实体；
③ 诚实报告——信号不足时不伪装确定性；
④ 患者利益优先——不输出合规红线外的词汇。

请解读下面这份 PPG 脉诊观测数据，给出：
1) 五形失衡最突出的方向（用 SPUM 关系网络拓扑语言）；
2) 可能的病理标签（用传统中医证型，诚实标注置信度）；
3) 组合模式（上热下寒 / 上实下虚 等）；
4) 简短调理方向（不写功效，只写生活方式建议）。"""

user = f"""PPG 脉诊观测（bridge 分析结果）：
- ΔF (五形变化量 ∈ [-1,1]): 木={bridge_df['wood']:+.3f}, 火={bridge_df['fire']:+.3f}, 土={bridge_df['earth']:+.3f}, 金={bridge_df['metal']:+.3f}, 水={bridge_df['water']:+.3f}
- v_obs (五形观测 ∈ [0,100]): {bridge_vobs}
- SQI (信号质量): {bridge_sqi}
- bridge 辨证: 心脉瘀阻（置信度42%），上热下寒，硬度跨视角不一致(一致性0.21)

注意：这份波形只有5个有效搏动（19s，检出率偏低），rate_score/smooth_score 不可信。"""

t0 = time.time()
try:
    r2 = httpx.post(
        'https://api.deepseek.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
        json={
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            'temperature': 0.3,
        },
        timeout=60,
    )
    dt = time.time() - t0
    print(f'HTTP {r2.status_code} | 用时 {dt:.1f}s')
    if r2.status_code == 200:
        content = r2.json()['choices'][0]['message']['content']
        print()
        print(content)
    else:
        print(f'错误: {r2.text[:500]}')
except Exception as e:
    print(f'DeepSeek 直接调用失败: {e}')
