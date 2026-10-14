"""wuxing_chain — 五边形凸多面体耦合链动力学检测

核心范式（来自 spum-core/五行/地元/spum-卦组合化解.md + 用户实战修正）：
  五边形 = SHENG 链（wood→fire→earth→metal→water→wood）
  稳定时每个节点输出=下游，反作用力均匀分配到其他 4 个顶点
  一旦某个顶点凹陷超过阈值 → 对受力点的反作用力瞬间消失 → 链条断了

  治理策略不是写死的"永不碰尖峰"——是优化问题：
    链条完整 → 直接压抑尖峰（反作用力还在，调尖峰有效）
    链条断裂 → 增益中庸节点（反作用力消失，必须先恢复链条）

这个模块只做"检测"——判断五边形当前的力学状态。
治理策略选择器（直接压抑 vs 增益中庸）调用检测结果做决策。
"""

from __future__ import annotations
from typing import Optional


# ═══════════════════════════════════════════════════════════
# 共享常量（与 reduction_engine / spacetime_engine 对齐）
# ═══════════════════════════════════════════════════════════

SHENG = {'wood': 'fire', 'fire': 'earth', 'earth': 'metal', 'metal': 'water', 'water': 'wood'}
KE    = {'wood': 'earth', 'earth': 'water', 'water': 'fire', 'fire': 'metal', 'metal': 'wood'}
WUXING_LIST = ['wood', 'fire', 'earth', 'metal', 'water']
WUXING_CN = {'wood': '木', 'fire': '火', 'earth': '土', 'metal': '金', 'water': '水'}


# ═══════════════════════════════════════════════════════════
# 力学状态检测
# ═══════════════════════════════════════════════════════════

def detect_chain_state(v: dict[str, float], threshold: float = 8.0) -> dict:
    """
    检测五边形耦合链的力学状态

    Args:
        v: 五形向量 {"wood": 50, "fire": 60, ...}（原始体质值或时空加权后值）
        threshold: 链条断裂阈值（默认 8.0）
                   最弱节点和次弱节点的差值 ≥ threshold → 链条断了
                   （用户："凹陷超过阈值 → 反作用力瞬间消失"）

    Returns:
        {
            'nodes': [...],              # 按值从小到大排序的五形
            'weakest': 'metal',          # 最弱节点（凹陷顶点）
            'second_weakest': 'wood',    # 次弱节点
            'strongest': 'fire',         # 最强节点（尖峰）
            'strength_gap': 30.0,        # 最强-最弱差
            'chain_broken': True/False,  # 链条是否断了
            'break_severity': 0.0-1.0,   # 断链严重程度（0=没断，1=完全断）
            'upstream_of_weakest': 'earth',  # 最弱节点的上游（生它的）
            'downstream_of_weakest': 'water', # 最弱节点的下游（它生的）
        }
    """
    nodes_sorted = sorted(WUXING_LIST, key=lambda n: v.get(n, 50))
    weakest = nodes_sorted[0]
    second = nodes_sorted[1]
    strongest = nodes_sorted[-1]

    gap_weak = v.get(second, 50) - v.get(weakest, 50)
    gap_total = v.get(strongest, 50) - v.get(weakest, 50)

    # 断裂判定：最弱和次弱差 ≥ threshold 或最弱低于绝对阈值
    abs_low = v.get(weakest, 50) < 30
    chain_broken = gap_weak >= threshold or abs_low

    # 断链严重程度（归一化到 0-1）
    if not chain_broken:
        break_severity = 0.0
    else:
        # 综合：gap_weak 超 threshold 的程度 + 最弱节点的绝对值
        excess = max(0, gap_weak - threshold)
        low_score = max(0, 30 - v.get(weakest, 50))
        break_severity = min(1.0, (excess / threshold) * 0.6 + (low_score / 20) * 0.4)

    # 上下游
    upstream = [k for k, val in SHENG.items() if val == weakest][0]  # 生 weakest 的
    downstream = SHENG[weakest]  # weakest 生的

    return {
        'nodes': nodes_sorted,
        'values': {n: v.get(n, 50) for n in nodes_sorted},
        'weakest': weakest,
        'second_weakest': second,
        'strongest': strongest,
        'strength_gap': round(gap_total, 1),
        'chain_broken': chain_broken,
        'break_severity': round(break_severity, 3),
        'break_gap': round(gap_weak, 1),
        'abs_low_violation': abs_low,
        'upstream_of_weakest': upstream,
        'downstream_of_weakest': downstream,
    }


def detect_ke_conflict(v: dict[str, float]) -> dict | None:
    """
    KE 链冲突检测：相克双方都偏旺 → 需要调和

    用户的实战锚点：金木相战（三六大壮）是典型 KE 冲突
      不是"金克木"——是金木都太旺，相克成了结构上的硬碰撞
      调和相位 = SHENG 链上的中间相位（金→水→木 → 水是调和）
    """
    for a, b in KE.items():
        if v.get(a, 50) > 58 and v.get(b, 50) > 58:
            mediator = SHENG[a]  # a 所生
            return {
                'a': a, 'b': b,
                'mediator': mediator,
                'mediator_cn': WUXING_CN.get(mediator),
                'severity': round(min(v.get(a, 50), v.get(b, 50)) - 60, 1),
            }
    return None


# ═══════════════════════════════════════════════════════════
# 治理策略选择器（核心！动态选择"直接压抑" vs "增益中庸"）
# ═══════════════════════════════════════════════════════════

def select_governance_strategy(chain_state: dict, 
                               ke_conflict: Optional[dict] = None,
                               context: Optional[dict] = None) -> dict:
    """
    动态选择治理策略——根据五边形力学状态决定

    核心逻辑：
      链条断裂 + 有 KE 冲突 → **增益中庸节点**（两件事都指向同一个调节相位）
      链条断裂（无 KE 冲突）→ **增益最弱节点**（让链条恢复）
      链条完整 + 强尖峰 → **直接压抑尖峰**（反作用力还在，压抑尖峰有效）
      链条完整 + 无尖峰 → **不干预**（链条自调节）

    Args:
        chain_state: detect_chain_state() 的输出
        ke_conflict: detect_ke_conflict() 的输出（None=无冲突）
        context: 可选额外上下文（如 KE 冲突相位是否就是 SHENG 断链相位）

    Returns:
        {
            'strategy': '增益中庸' | '压抑尖峰' | '不干预',
            'target_node': 'metal' | None,
            'target_role': '调和相位' | '最弱节点' | '尖峰节点' | None,
            'reason': '...',
            'confidence': 0.0-1.0,
        }
    """
    broken = chain_state['chain_broken']
    severity = chain_state['break_severity']
    weakest = chain_state['weakest']
    strongest = chain_state['strongest']
    gap = chain_state['strength_gap']

    # 场景 1：链条断了 + KE 冲突 → 增益 KE 调和相位（优先）
    if broken and ke_conflict:
        # 如果 KE 调和相位恰好就是 SHENG 最弱节点 → 评分加倍（两个信号指向同一节点）
        if ke_conflict['mediator'] == weakest:
            return {
                'strategy': '增益中庸',
                'target_node': weakest,
                'target_role': '调和相位·最弱节点',
                'reason': (
                    f'链条断于{WUXING_CN[weakest]}形 + KE链{WUXING_CN[ke_conflict["a"]]}克'
                    f'{WUXING_CN[ke_conflict["b"]]}——调和相位与断链点重合，增益效果最优'
                ),
                'confidence': min(1.0, 0.9 + ke_conflict['severity'] * 0.01),
            }
        # 否则：链条断于 A，KE 需调和 B——优先处理链条断裂（更底层）
        return {
            'strategy': '增益中庸',
            'target_node': weakest,
            'target_role': '最弱节点',
            'reason': (
                f'链条断于{WUXING_CN[weakest]}形（凹陷过阈值，反作用力消失），'
                f'且存在KE冲突——先恢复链条自调节能力'
            ),
            'confidence': min(1.0, 0.7 + severity * 0.2),
        }

    # 场景 2：链条断了（无 KE 冲突）→ 增益最弱节点
    if broken:
        return {
            'strategy': '增益中庸',
            'target_node': weakest,
            'target_role': '最弱节点',
            'reason': (
                f'链条断于{WUXING_CN[weakest]}形（凹陷过阈值，反作用力消失）——'
                f'增益{WUXING_CN[weakest]}让五边形凸多面体恢复自调节'
            ),
            'confidence': min(1.0, 0.8 + severity * 0.2),
        }

    # 场景 3：链条完整（无断裂）+ 有 KE 冲突 → 增益调和相位
    if ke_conflict:
        return {
            'strategy': '增益中庸',
            'target_node': ke_conflict['mediator'],
            'target_role': '调和相位',
            'reason': (
                f'链条完整但存在KE冲突（{WUXING_CN[ke_conflict["a"]]}克'
                f'{WUXING_CN[ke_conflict["b"]]}）——增益调和相位'
                f'{WUXING_CN[ke_conflict["mediator"]]}形缓冲'
            ),
            'confidence': min(1.0, 0.5 + ke_conflict['severity'] * 0.03),
        }

    # 场景 4：链条完整 + 强尖峰 → 直接压抑尖峰
    # 反作用力还在，压抑尖峰可以让其他 4 点自然分担
    if gap >= 15 and chain_state.get('second_weakest', '') != strongest:
        # 尖峰显著高于其他 → 压抑
        second_strongest = chain_state['nodes'][-2]  # 排序后倒数第二
        if v_diff(chain_state['values'], strongest, second_strongest) >= 8:
            return {
                'strategy': '压抑尖峰',
                'target_node': strongest,
                'target_role': '尖峰节点',
                'reason': (
                    f'链条完整（反作用力均匀分配中），{WUXING_CN[strongest]}形显著高于其他——'
                    f'直接压抑尖峰，反作用力自然重新分配'
                ),
                'confidence': 0.6,
            }

    # 场景 5：链条完整 + 无尖峰 → 不干预
    return {
        'strategy': '不干预',
        'target_node': None,
        'target_role': None,
        'reason': f'五边形凸多面体力学自洽，当前无需干预（最大差 {gap:.1f} 在阈值内）',
        'confidence': 0.8,
    }


def v_diff(values: dict, a: str, b: str) -> float:
    return abs(values.get(a, 50) - values.get(b, 50))


# ═══════════════════════════════════════════════════════════
# 快速验证：5 种典型五边形状态
# ═══════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=== 五边形凸多面体治理策略选择器验证 ===\n")

    # 场景 1：链断+KE冲突 重合（三六大壮·金木相战·水最弱）
    print("【1】链断+KE冲突重合（典型大壮象）")
    v1 = {'wood': 65, 'fire': 50, 'earth': 48, 'metal': 70, 'water': 30}
    cs1 = detect_chain_state(v1)
    ke1 = detect_ke_conflict(v1)
    st1 = select_governance_strategy(cs1, ke1)
    print(f"  v={v1}")
    print(f"  chain_broken={cs1['chain_broken']}, weakest={cs1['weakest']}, break_severity={cs1['break_severity']}")
    print(f"  ke_conflict={ke1}")
    print(f"  → 策略={st1['strategy']}, target={st1['target_node']}({st1['target_role']})")
    print(f"  → {st1['reason']}\n")

    # 场景 2：链断（土最弱·土壅）
    print("【2】链断（土最弱·土壅，金桥弱）")
    v2 = {'wood': 50, 'fire': 50, 'earth': 25, 'metal': 55, 'water': 50}
    cs2 = detect_chain_state(v2)
    ke2 = detect_ke_conflict(v2)
    st2 = select_governance_strategy(cs2, ke2)
    print(f"  v={v2}")
    print(f"  chain_broken={cs2['chain_broken']}, weakest={cs2['weakest']}")
    print(f"  → 策略={st2['strategy']}, target={st2['target_node']}({st2['target_role']})")
    print(f"  → {st2['reason']}\n")

    # 场景 3：链条完整+强尖峰（木形过亢，链条没断）
    print("【3】链条完整+木形尖峰（链条没断，反作用力还在）")
    v3 = {'wood': 75, 'fire': 58, 'earth': 55, 'metal': 52, 'water': 50}
    cs3 = detect_chain_state(v3)
    ke3 = detect_ke_conflict(v3)
    st3 = select_governance_strategy(cs3, ke3)
    print(f"  v={v3}")
    print(f"  chain_broken={cs3['chain_broken']}, strongest={cs3['strongest']}, gap={cs3['strength_gap']}")
    print(f"  → 策略={st3['strategy']}, target={st3['target_node']}({st3['target_role']})")
    print(f"  → {st3['reason']}\n")

    # 场景 4：链条完整+无尖峰
    print("【4】链条完整+无尖峰（自调节中）")
    v4 = {'wood': 52, 'fire': 48, 'earth': 50, 'metal': 53, 'water': 47}
    cs4 = detect_chain_state(v4)
    st4 = select_governance_strategy(cs4)
    print(f"  v={v4}")
    print(f"  chain_broken={cs4['chain_broken']}, gap={cs4['strength_gap']}")
    print(f"  → 策略={st4['strategy']}")
    print(f"  → {st4['reason']}\n")

    # 场景 5：链断+KE冲突不重合（断在土，冲突在金木）
    print("【5】链断（土最弱）+ KE冲突（金木战）不重合")
    v5 = {'wood': 65, 'fire': 48, 'earth': 28, 'metal': 62, 'water': 50}
    cs5 = detect_chain_state(v5)
    ke5 = detect_ke_conflict(v5)
    st5 = select_governance_strategy(cs5, ke5)
    print(f"  v={v5}")
    print(f"  weakest={cs5['weakest']}, KE={ke5['a']}{ke5['b']}")
    print(f"  → 策略={st5['strategy']}, target={st5['target_node']}({st5['target_role']})")
    print(f"  → {st5['reason']}\n")

    print("🎉 五边形凸多面体治理策略选择器验证通过！")
