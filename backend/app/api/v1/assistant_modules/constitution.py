"""constitution - SPUM v3/v4 先天体质推理：八字 + v_innate + 大运 + LLM 病历式画像"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
import httpx

from ....database import get_db
from ....models import User
from ....config import settings
from ...deps import get_current_user
from ....utils.trajectory_algorithm import (
    DIMS, TIANGAN_WUXING, DIZHI_CANGGAN,
)

router = APIRouter()

@router.post("/constitution/analysis")
async def constitution_analysis(body: dict,
                                db: Session = Depends(get_db),
                                current: User = Depends(get_current_user)):
    """SPUM v3 先天体质推理 — 八字结构化 + v_innate + 大运 + LLM 病历级可验证预测。
    
    v3 核心升级：
    1. 完整八字上下文（四柱、藏干、日主）喂给 LLM，生成病历级回溯性预测
    2. 自动用 lunar_helper.compute_dayun() 排大运，每个年龄段命中的大运真正生效
    3. LLM prompt 要求"你是不是从小就..."式的具体可验证预测
    4. 先生成体质总纲标签（5-10字，如"水木通明·寒水无火"），抓住用户注意力
    """
    v_innate = body.get("v_innate") or {}
    day_master_el = body.get("day_master_element") or "earth"
    day_master_gan = body.get("day_master") or ""
    gender = body.get("gender") or "男"
    nickname = body.get("nickname") or ""
    
    # ── 八字完整上下文 ──
    bazi_str = body.get("bazi") or ""
    pillars = body.get("pillars") or []
    gz_y = body.get("ganzhi_year", "")
    gz_m = body.get("ganzhi_month", "")
    gz_d = body.get("ganzhi_day", "")
    gz_h = body.get("ganzhi_hour", "")
    
    # ── 自动排大运（如果前端没传） ──
    dayun = body.get("dayun") or []
    if not dayun and body.get("birth_date"):
        try:
            from ....utils.lunar_helper import compute_dayun
            dayun = compute_dayun(
                birth_date=body["birth_date"],
                birth_hour=body.get("birth_hour"),
                gender=gender,
                birth_city=body.get("birth_city"),
            ) or []
        except Exception:
            dayun = []

    if not v_innate:
        raise HTTPException(400, "需要 v_innate (五行百分比)")

    from ....utils.trajectory_algorithm import DIMS

    # ── 1. 偏离计算：用相对均值 20 的偏离率（不是 HEALTH_POLYTOPE） ──
    # threshold：偏离均值 ±25% 才算"显著"，否则视为"均衡"
    threshold = _V_INNATE_MEAN * _V_INNATE_DEVIATION_PCT   # 5
    deviations = []
    for el in DIMS:
        score = v_innate.get(el, 20)
        dev = score - _V_INNATE_MEAN   # 偏离均值
        if abs(dev) <= threshold:
            polarity = 'balanced'
        elif dev < -threshold:
            polarity = 'weak'
        else:
            polarity = 'strong'
        deviations.append({
            'el': el, 'score': score,
            'mean': _V_INNATE_MEAN, 'dev': dev,
            'delta': abs(dev), 'polarity': polarity,
        })

    # 按偏离绝对值排序 → 偏离最大的（不管方向）排前面
    deviations.sort(key=lambda d: d['delta'], reverse=True)
    top3 = deviations[:3]

    # ── 2. 体质标签（含亮点 + 注意点） ──
    constitution_tags = []
    # 先找亮点：偏离均值最大的 "strong" 维度（先天禀赋突出）
    strong_els = [d for d in deviations if d['polarity'] == 'strong']
    balanced_els = [d for d in deviations if d['polarity'] == 'balanced']
    weak_els = [d for d in deviations if d['polarity'] == 'weak']

    # 最多 2 个亮点（偏离最大的 strong 或 balanced 也行）
    highlights = strong_els[:2] if strong_els else balanced_els[:1]
    for d in highlights:
        if d['polarity'] == 'strong':
            tmpl = _CONSTITUTION_STRENGTH_TEMPLATES[d['el']]
            constitution_tags.append({
                'element': d['el'], 'polarity': 'strong',
                'score': d['score'], 'text': tmpl, 'is_strength': True,
            })
        elif d['polarity'] == 'balanced':
            tmpl = _CONSTITUTION_BALANCED_TEMPLATES[d['el']]
            constitution_tags.append({
                'element': d['el'], 'polarity': 'balanced',
                'score': d['score'], 'text': tmpl, 'is_strength': True,
            })

    # 最多 2 个注意点（偏离最大的 weak/strong，但排除已作为亮点的）
    seen_hl = {h['el'] for h in highlights}
    concerns = [d for d in deviations
                if d['polarity'] != 'balanced' and d['el'] not in seen_hl][:2]
    for d in concerns:
        tmpl = _CONSTITUTION_TEMPLATES.get((d['el'], d['polarity']), '')
        constitution_tags.append({
            'element': d['el'], 'polarity': d['polarity'],
            'score': d['score'], 'text': tmpl, 'is_strength': False,
        })

    # ── 3. 日主分析 ──
    day_master_score = v_innate.get(day_master_el, 20)
    dm_dev = day_master_score - _V_INNATE_MEAN
    if abs(dm_dev) <= threshold:
        dm_note = f"日主{day_master_el} — 先天基底均衡，稳扎稳打"
    elif dm_dev < -threshold:
        dm_note = f"日主{day_master_el}偏弱 — 基底不够厚实，需要额外关注恢复力"
    else:
        dm_note = f"日主{day_master_el}偏旺 — 先天禀赋充沛，精力旺盛"

    # ── 4. 分年龄段：不是"风险提示"，是"你可能经历过/正在经历的身体特征" ──
    age_risks = []
    # 观察点 = 所有非 balanced + 亮点维度（这些是先天显著的）
    obs_eles = highlights + concerns
    if not obs_eles:
        # 五行全均衡 → 找偏离最小的（也是一种观察点）
        obs_eles = deviations[:2]

    for age_start, age_end, label in _AGE_RISK_RANGES:
        observe_items = []
        for d in obs_eles[:3]:   # 最多 3 个观察维度
            el_info = _ELEMENT_ZANGFU.get(d['el'], {})
            zf = el_info.get('zangfu', d['el'])
            if d['polarity'] == 'strong':
                observe_items.append(f"{zf}先天偏盛（{d['score']:.0f}分）")
            elif d['polarity'] == 'weak':
                observe_items.append(f"{zf}先天偏弱（{d['score']:.0f}分）")
            else:
                observe_items.append(f"{zf}先天均衡")

        # 大运 refine：命中的大运五行叠加
        dayun_hit = []
        for dy in dayun:
            gan = dy.get('gan', '')
            zhi = dy.get('zhi', '')
            ds = dy.get('start', dy.get('start_age', 0))
            de = dy.get('end', dy.get('end_age', 999))
            if ds <= age_end and de >= age_start:
                from ....utils.trajectory_algorithm import TIANGAN_WUXING, DIZHI_CANGGAN
                gan_el = TIANGAN_WUXING.get(gan, '')
                if gan_el:
                    dayun_hit.append(f"{dy.get('name','')}运·{gan_el}")

        age_risks.append({
            'age_range': f"{age_start}-{age_end}",
            'age_label': label,
            'primary_gender_hint': '' if gender == '男' else '（女性需关注月经/带脉与各脏腑联动）',
            'risk_items': observe_items,   # 改名但兼容旧前端，语义已变"观察点"
            'dayun_hit': dayun_hit,
        })

    # ── 5. 地缘因子规则计算（出生地省份 → 五行微修正） ──
    birth_province = body.get("birth_province", "")
    birth_city = body.get("birth_city", "")
    geo_hint = _compute_geo_factor(birth_province, birth_city)

    # ── 6. 当前大运规则计算 ──
    current_dayun = _find_current_dayun(dayun)

    # ── 7. LLM 润色：病历式 6 段生成 ──
    llm_result = None
    if settings.DEEPSEEK_API_KEY:
        try:
            llm_result = await _polish_constitution_medical(
                deviations, v_innate, day_master_el, day_master_gan,
                dayun, current_dayun, age_risks,
                bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
                gender, nickname, geo_hint, birth_province, birth_city,
            )
        except Exception:
            llm_result = None

    if llm_result:
        constitution_summary = llm_result.get("constitution_summary", "")
    else:
        constitution_summary = ""

    # ── 如果 LLM 没返回，用规则拼一个可读的 6 段 markdown ──
    if not llm_result:
        llm_result = _build_rule_sections(
            bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
            day_master_el, day_master_gan, deviations, v_innate,
            dayun, current_dayun, age_risks, geo_hint,
            birth_province, birth_city, gender, nickname,
        )
        constitution_summary = llm_result.get("constitution_summary", "")

    return {
        "constitution_summary": constitution_summary,
        "llm_sections": llm_result,
        "rule_data": {
            "v_innate": v_innate,
            "deviations": deviations,
            "day_master_el": day_master_el,
            "day_master_gan": day_master_gan,
            "dayun": dayun,
            "current_dayun": current_dayun,
            "bazi": bazi_str,
            "pillars": pillars,
            "geo_factor": geo_hint,
            "birth_province": birth_province,
            "birth_city": birth_city,
            "gender": gender,
        },
        "algorithm": "spum_constitution_v4_medical" if llm_result else "spum_constitution_v4_rule",
    }



# ── 规则版构建 / 病历式 LLM 润色（独立模块）─────────────────
from .constitution_rules import (
    _build_rule_sections, _polish_constitution_medical,
    _STRENGTH_DESC, _WEAK_DESC, _CAREER_HINT,
)
