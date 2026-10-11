"""constitution_rules - 先天体质画像：规则版 markdown 构建 + 病历式 LLM 润色"""
import json
import httpx

from ....config import settings

def _build_rule_sections(
    bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
    day_master_el, day_master_gan, deviations, v_innate,
    dayun, current_dayun, age_risks, geo_hint,
    birth_province, birth_city, gender, nickname,
) -> dict:
    """规则版 6 段 markdown — 无 LLM 时的保底输出。"""
    
    # 五行中文名
    _EL_CN = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
    _EL_EMOJI = {"wood": "🌲", "fire": "🔥", "earth": "🪨", "metal": "⚙️", "water": "💧"}

    # ── ① 八字排盘 ──
    bazi_md = f"""### 公农历转换

| 项目 | 内容 |
|------|------|
| 八字 | **{bazi_str or '（未推演）'}** |
| 四柱 | 年柱 **{gz_y}** · 月柱 **{gz_m}** · 日柱 **{gz_d}** · 时柱 **{gz_h}** |

### 五行分布

| 五行 | SPUM 值 | 偏离均值 | 状态 |
|------|:-------:|:-------:|:----:|
"""
    for d in deviations:
        el_cn = _EL_CN.get(d['el'], d['el'])
        arrow = "↑" if d['polarity'] == 'strong' else "↓" if d['polarity'] == 'weak' else "→"
        state = "偏旺" if d['polarity'] == 'strong' else "偏弱" if d['polarity'] == 'weak' else "均衡"
        bazi_md += f"| {_EL_EMOJI.get(d['el'],'')} {el_cn} | {d['score']:.0f} | {d['dev']:+.0f}{arrow} | {state} |\n"
    bazi_md += f"""
### 日主

日干 **{day_master_gan}**（{_EL_CN.get(day_master_el, day_master_el)}形）——先天基底的核心。
"""

    # ── ② 先天基底推估 ──
    innate_md = "### 五形先天基底\n\n"
    # 先列亮点
    strengths = [d for d in deviations if d['polarity'] == 'strong']
    weaknesses = [d for d in deviations if d['polarity'] == 'weak']
    balanced = [d for d in deviations if d['polarity'] == 'balanced']
    
    if strengths:
        innate_md += "**✨ 天生优势（先天偏旺）：**\n\n"
        for s in strengths:
            el_cn = _EL_CN.get(s['el'], s['el'])
            innate_md += f"- **{el_cn}形偏旺**（{s['score']:.0f}分）——{_STRENGTH_DESC.get(s['el'], '先天禀赋充沛')}\n"
        innate_md += "\n"
    
    if balanced:
        innate_md += "**⚖️ 先天均衡：**\n\n"
        for b in balanced:
            el_cn = _EL_CN.get(b['el'], b['el'])
            innate_md += f"- **{el_cn}形均衡**（{b['score']:.0f}分）——先天禀赋平衡稳定\n"
        innate_md += "\n"
    
    if weaknesses:
        innate_md += "**👀 先天观察点（先天偏弱）：**\n\n"
        for w in weaknesses:
            el_cn = _EL_CN.get(w['el'], w['el'])
            innate_md += f"- **{el_cn}形偏弱**（{w['score']:.0f}分）——{_WEAK_DESC.get(w['el'], '先天禀赋相对不足')}\n"
    
    # ── ③ 地缘因子修正 ──
    geo_md = f"### 出生地：{birth_province or '（未填）'}{' ' + birth_city if birth_city else ''}\n\n"
    geo_md += f"{geo_hint.get('note', '地缘因子未计算')}\n\n"
    correction = geo_hint.get('correction', {})
    if correction:
        geo_md += "**外环境五行修正方向：**\n\n"
        for el, sign in correction.items():
            arrow = "↑ 天然加强" if sign == "+" else "↓ 天然减弱"
            geo_md += f"- {el}形：{arrow}\n"
    geo_md += "\n地缘修正效应：出生地的气候、水土、饮食会对先天八字格局产生长期微调。\n"

    # ── ④ 姓名与职业因子（规则版简版） ──
    name_md = f"### 昵称：{nickname or '（未填）'}\n\n"
    name_md += "姓名用字的五行属性会对先天体质产生微弱但长期的微调效应。"
    name_md += "当前为规则版输出，姓名五行修正需结合用字康熙字典笔画与偏旁部首综合判断。\n\n"
    # 从格局推断适合的方向
    if strengths:
        top_el = strengths[0]['el']
        name_md += f"### 天然适合的方向（基于最强五行 {_EL_CN.get(top_el, top_el)} 形）\n\n"
        career = _CAREER_HINT.get(top_el, "")
        if career:
            name_md += f"- {career}\n"

    # ── ⑤ 大运排盘与当前大运 ──
    dayun_md = "### 大运排盘\n\n"
    if dayun:
        dayun_md += "| 大运 | 年龄段 |\n|------|--------|\n"
        for dy in dayun[:10]:
            ds = dy.get('start', dy.get('start_age', '?'))
            de = dy.get('end', dy.get('end_age', '?'))
            ganzhi = dy.get('gan', '') + dy.get('zhi', '')
            marker = " ◀ **当前**" if dy.get('gan','') + dy.get('zhi','') == (current_dayun.get('gan','') + current_dayun.get('zhi','')) else ""
            dayun_md += f"| {ganzhi}{marker} | {ds}-{de}岁 |\n"
    else:
        dayun_md += "大运排盘数据未生成。\n"
    
    if current_dayun:
        dayun_md += f"\n### 当前大运分析\n\n"
        gz = current_dayun.get('gan','') + current_dayun.get('zhi','')
        ds = current_dayun.get('start', current_dayun.get('start_age', '?'))
        de = current_dayun.get('end', current_dayun.get('end_age', '?'))
        dayun_md += f"当前年龄段命中 **{gz}** 大运（{ds}-{de}岁）。\n"
        el = TIANGAN_WUXING.get(current_dayun.get('gan', ''), '') if current_dayun else ''
        if el:
            dayun_md += f"大运天干 {current_dayun.get('gan','')} 属 **{_EL_CN.get(el, el)}形**，"
            if el in [s['el'] for s in strengths]:
                dayun_md += "与先天偏旺之形叠加，该形力量进一步增强。\n"
            elif el in [w['el'] for w in weaknesses]:
                dayun_md += "对先天偏弱之形有天然补益。\n"
            else:
                dayun_md += "与先天格局形成稳定调和。\n"

    # ── ⑥ 先天体质倾向 ──
    summary = ""
    if strengths and weaknesses:
        top_s = _EL_CN.get(strengths[0]['el'], strengths[0]['el'])
        top_w = _EL_CN.get(weaknesses[0]['el'], weaknesses[0]['el'])
        summary = f"{top_s}{top_s}通明 · {top_w}弱格局"
    elif strengths:
        summary = f"{_EL_CN.get(strengths[0]['el'], '')}形偏旺格局"
    elif weaknesses:
        summary = f"{_EL_CN.get(weaknesses[0]['el'], '')}形偏弱格局"
    else:
        summary = "五行均衡格局"

    constitution_md = f"### 体质总纲\n\n**{summary}**\n\n"
    constitution_md += "### 核心体质特征\n\n"
    
    constitution_md += "**✨ 先天优势：**\n\n"
    if strengths:
        for s in strengths[:2]:
            el_cn = _EL_CN.get(s['el'], s['el'])
            constitution_md += f"- {el_cn}形先天偏旺 → {_STRENGTH_DESC.get(s['el'], '')}\n"
    if balanced:
        constitution_md += f"- 五行有均衡之形 → 先天禀赋中有稳定的恢复力与适应力\n"
    
    constitution_md += "\n**👀 先天倾向：**\n\n"
    if weaknesses:
        for w in weaknesses[:3]:
            el_cn = _EL_CN.get(w['el'], w['el'])
            constitution_md += f"- {el_cn}形先天偏弱 → {_WEAK_DESC.get(w['el'], '')}\n"
    if not weaknesses:
        constitution_md += "- 五行先天无明显偏衰，整体禀赋稳定\n"

    return {
        "constitution_summary": summary,
        "sections": {
            "bazi_analysis": bazi_md,
            "innate_base": innate_md,
            "geo_factor": geo_md,
            "name_career": name_md,
            "dayun_current": dayun_md,
            "constitution_summary_detail": constitution_md,
        }
    }


# ── 规则版描述表 ──
_STRENGTH_DESC = {
    "wood": "思维架构能力强，能快速构建复杂思想体系，思虑深邃有远见",
    "fire": "行动力充沛，热情有感染力，做事有冲劲，精力恢复快",
    "earth": "承载能力强，稳定可靠，消化与储备系统功能扎实",
    "metal": "决断力强，执行效率高，收敛与肃降功能顺畅",
    "water": "智慧深邃，内省能力强，精神层面恢复力好，思维有穿透力",
}
_WEAK_DESC = {
    "wood": "思虑能力相对弱，复杂思维架构需要更多后天训练，情绪弹性偏弱",
    "fire": "行动力与驱动力偏弱，怕冷，末梢循环可能不足，需要更多温暖",
    "earth": "消化功能易受影响，承载能力偏弱，压力大时先影响胃口",
    "metal": "收敛与执行能力偏弱，决断有时犹豫不决，肺气与皮肤屏障功能需要关注",
    "water": "智慧深度与内省能力偏弱，精神层面恢复力需要更多时间，精力易累",
}
_CAREER_HINT = {
    "wood": "天然适合思想建构、教育、写作、策划类工作",
    "fire": "天然适合创意表达、销售、领导、表演类工作",
    "earth": "天然适合管理、建筑、农业、稳定运营类工作",
    "metal": "天然适合金融、法律、机械、精密执行类工作",
    "water": "天然适合研究、哲学、心理、深度分析类工作",
}


def _compute_geo_factor(province: str, city: str = "") -> dict:
    """规则算地缘因子 — 出生地经纬度→气候→对五行的微调方向。
    
    简化版：按省份划分气候带，给出五行修正方向。
    例：陕西(西北) → 土厚金重 → 对木旺格局有天然制衡
    """
    if not province:
        return {"note": "未填写出生地，地缘因子暂未计算", "correction": {}}
    
    # 简化气候-五行映射（规则版）
    _REGION_WUXING = {
        # 西北：黄土高原 → 土金厚
        "陕西": {"土": "+", "金": "+", "水": "-"},
        "甘肃": {"土": "+", "金": "+", "水": "-"},
        "宁夏": {"土": "+", "金": "+"},
        "青海": {"土": "+", "水": "+"},
        "新疆": {"金": "+", "水": "-"},
        # 华北：平原 → 土厚
        "北京": {"土": "+", "金": "+"},
        "天津": {"土": "+", "水": "+"},
        "河北": {"土": "+"},
        "山西": {"土": "+", "金": "+"},
        "山东": {"土": "+", "水": "+"},
        "河南": {"土": "+"},
        # 东北：寒冷 → 水重
        "辽宁": {"水": "+", "土": "+"},
        "吉林": {"水": "+"},
        "黑龙江": {"水": "+"},
        # 华东：水网 → 水木重
        "上海": {"水": "+", "木": "+"},
        "江苏": {"水": "+", "木": "+"},
        "浙江": {"水": "+", "木": "+"},
        "安徽": {"土": "+", "木": "+"},
        "江西": {"木": "+"},
        "福建": {"木": "+", "火": "+"},
        # 华中：过渡带
        "湖北": {"水": "+", "土": "+"},
        "湖南": {"木": "+", "火": "+"},
        # 华南：湿热 → 火土重
        "广东": {"火": "+", "土": "+", "水": "+"},
        "广西": {"土": "+", "火": "+"},
        "海南": {"火": "+", "土": "+"},
        # 西南：复杂地貌
        "四川": {"土": "+", "水": "+", "木": "+"},
        "贵州": {"土": "+"},
        "云南": {"木": "+", "火": "+"},
        "西藏": {"金": "+", "土": "+"},
        # 直辖市/特别行政区 fallback
        "重庆": {"土": "+", "水": "+"},
    }
    correction = _REGION_WUXING.get(province, {})
    
    if correction:
        hint = f"{province}"
        if city:
            hint += f"（{city}）"
        hint += " — "
        parts = []
        for el, sign in correction.items():
            arrow = "↑" if sign == "+" else "↓"
            parts.append(f"{el}形{arrow}")
        hint += "外环境" + "、".join(parts)
    else:
        hint = f"{province}"
        if city:
            hint += f"（{city}）"
    
    return {"note": hint, "correction": correction}


def _find_current_dayun(dayun_list: list) -> dict:
    """从大运排盘找当前命中的大运（基于当前年龄）。"""
    import datetime
    now = datetime.datetime.now()
    current_year = now.year
    
    for dy in dayun_list:
        ds = dy.get('start', dy.get('start_age', 0))
        de = dy.get('end', dy.get('end_age', 999))
        # 如果大运用 start_year/end_year
        sy = dy.get('start_year', 0)
        ey = dy.get('end_year', 0)
        
        if sy and ey and sy <= current_year <= ey:
            return dy
        if ds and de and ds <= current_year <= de:
            return dy
    
    return dayun_list[0] if dayun_list else {}


async def _polish_constitution_medical(
    deviations, v_innate, day_master_el, day_master_gan,
    dayun, current_dayun, age_risks,
    bazi_str, pillars, gz_y, gz_m, gz_d, gz_h,
    gender, nickname, geo_hint, birth_province, birth_city,
) -> dict:
    """病历式 6 段体质画像生成 — 禁建议词，只描述不指导。"""
    import httpx

    # ── 大运格式化 ──
    dayun_lines = []
    for dy in dayun[:12]:
        ds = dy.get('start', dy.get('start_age', '?'))
        de = dy.get('end', dy.get('end_age', '?'))
        ganzhi = dy.get('gan', '') + dy.get('zhi', '')
        name = dy.get('name', '')
        year_range = dy.get('year_range', '')
        marker = " ◀ 当前大运" if dy.get('gan','') + dy.get('zhi','') == (current_dayun.get('gan','') + current_dayun.get('zhi','')) else ""
        dayun_lines.append(f"  {ganzhi} ({ds}-{de}岁 {year_range}) {name}{marker}")

    # ── 五行偏离格式化 ──
    dev_lines = []
    for d in deviations:
        dev_lines.append(f"  {d['el']}: {d['score']:.0f}分 (偏离均值{d['dev']:+.0f} → {d['polarity']})")

    # ── pillars 格式化 ──
    pillar_lines = []
    for p in pillars:
        if isinstance(p, dict):
            gan = p.get('gan', '') or p.get('tian_gan', '')
            zhi = p.get('zhi', '') or p.get('di_zhi', '')
            hidden = p.get('hidden', '') or p.get('cang_gan', '')
            label = p.get('label', '')
            pillar_lines.append(f"  {label}: {gan}({zhi}) 藏干[{hidden}]")
    
    prompt_lines = [
        "你是一位中医体质分析师，正在为一位用户撰写「先天体质画像」——",
        "要求达到专业病历的深度（参考：青囊中医病历雷苗苗版本）。",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 输出结构：严格 6 段病历式",
        "═══════════════════════════════════════════════════════════",
        "",
        "你必须按以下 6 段结构返回，每段用 markdown 写：",
        "",
        "### 第一段：八字排盘",
        "  - 公农历转换（农历→公历→节气边界→年/月/日/时柱干支推导）",
        "  - 四柱明细（天干/地支/藏干/纳音）",
        "  - 五行分布统计（天干+地支主气+藏干余气→总加权→旺衰判定）",
        "  - 格局判定（日干旺衰→格局名称→用神/忌神→特殊组合标注）",
        "",
        "### 第二段：先天基底推估",
        "  - 八字 → 五形 S 向量映射（SPUM 术语：S_木↑↑ 表示木形极度亢进）",
        "  - S_0^(0) 先天基底（五形各自的强度 + 先天影响描述）",
        "  - 日干五形人格倾向（先天体质倾向 + 易偏亢/易偏衰之形 + 人格特征）",
        "",
        "### 第三段：地缘因子修正",
        "  - 出生地省份 + 外环境对八字格局的修正效应",
        "  - 气候/水土/饮食对五行的微调",
        "  - 地缘修正结论",
        "",
        "### 第四段：姓名与职业因子修正",
        "  - 姓名用字的五行属性修正（如果能从名字推断的话）",
        "  - 职业/生活环境对体质的影响（从八字格局推断天然适合的方向）",
        "  - 修正结论",
        "",
        "### 第五段：大运流年排盘与当前大运分析",
        "  - 大运排布表（逆排/顺排 + 起运年龄 + 各运年龄段）",
        "  - 当前大运分析（当前年龄段命中的大运干支 + 对格局的影响）",
        "  - 流年参考（如果今年有特殊五行叠加）",
        "",
        "### 第六段：先天体质倾向与核心体质特征",
        "  - 体质总纲标签（如：水木通明·寒水无火格局）",
        "  - 核心体质特征（先夸 2-3 条天生优势，再写 2-3 条需要注意的先天倾向）",
        "  - 各系统的先天倾向（神经系统/心循环/脾消化/肺呼吸/肝胆/肾生殖 — 每项给先天倾向 + 风险等级 ★）",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 严禁事项（违反任何一条即降级）",
        "═══════════════════════════════════════════════════════════",
        "❌ 严禁给建议（禁止词：应该、要、必须、多、少、注意、别、避免、建议、推荐）",
        "❌ 严禁说将来（禁止词：将来、以后、要小心、预防）",
        "❌ 严禁用医生口吻（禁止词：诊断、治疗、处方、开药、就医）",
        "❌ 严禁恐吓（禁止词：容易得、高发、风险很大、危险）",
        "❌ 每段必须夸至少 1 条天生的优势（格局亮点、禀赋优点、人格长处）",
        "❌ 不要说'你容易...'，要说'你是不是从小就...'或'这个阶段你有没有...'",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 写作指南（每段必须遵守）",
        "═══════════════════════════════════════════════════════════",
        "",
        "### 语气",
        "- 像一位懂中医体质的老朋友在聊「你是不是从小就...」",
        "- 用回溯性问句或陈述句（过去/现在），不用将来时",
        "- 每段至少 1 条正向描述（天生优势、格局亮点）",
        "",
        "### 段落深度（参考专业病历标准）",
        "- 八字排盘：不能只列干支，要推导——谁当令、谁透出、谁被克、格局叫什么、用神忌神是谁",
        "- 先天基底：每个五行形要有「强度词」（极度亢进/偏旺/均衡/偏弱/严重不足）+「先天影响描述」（这个形旺/弱意味着什么）",
        "- 地缘因子：不能只说「广东→火↑」，要说具体效应——广东湿热对八字火弱的人是天然补偿，但对火旺的人是加剧",
        "- 大运分析：不能只列干支，要说这个运的五行与先天格局的关系——是补益？是加剧？是调和？",
        "- 核心特征：要写出具体的「生活场景」而不是抽象术语。不说「木形偏旺」，说「脑子里好像有个停不下来的建筑师」",
        "",
        "### 禁止事项（违反任何一条即降级）",
        "❌ 禁止复制或模仿任何具体人名、具体八字特征、具体格局名称（水木通明、寒水无火等）——那些只属于原始病历",
        "❌ 禁止说将来（禁止词：将来、以后、要小心、预防）",
        "❌ 禁止给建议（禁止词：应该、要、多、少、注意、别、避免、建议、推荐）",
        "❌ 禁止医生口吻（禁止词：诊断、治疗、处方、开药、就医）",
        "❌ 禁止恐吓（禁止词：容易得、高发、风险很大、危险）",
        "",
        "### 参考句式（仅供语气参考，内容必须来自当前用户数据）",
        "- 八字排盘：「[日干]在[月令]处[旺衰]，但天干[藏干]透出，身[旺衰]——[五行相生相克关系]为用，[五行不足]为忌」",
        "- 先天基底：「[五行]↑↑（极度亢进）——[地支组合]当令，先天[对应人格特征]极强，但[对应副作用]」",
        "- 地缘因子：「[省份]出生的[地貌特征]环境，是[八字格局]的天然[制衡/补偿/加剧]」",
        "- 大运分析：「[干支]运（[起运]-[止运]岁）[五行生克]——[对当前格局的影响]」",
        "- 核心特征：「你是不是从小就[具体生活感受1]？但同时又[具体生活感受2]——这就是[格局总纲]的典型表现」",
        "",
        "═══════════════════════════════════════════════════════════",
        "## 用户原始数据",
        "═══════════════════════════════════════════════════════════",
        f"昵称: {nickname or '(未填)'}  |  性别: {gender}",
        f"八字: {bazi_str or '(未推演)'}",
        f"四柱: 年[{gz_y}] 月[{gz_m}] 日[{gz_d}] 时[{gz_h}]",
        f"日主: {day_master_gan}({day_master_el})",
        f"",
        f"四柱明细:",
        *(pillar_lines or ["  (无)"]),
        f"",
        f"v_innate(五行分布,和=100): {v_innate}",
        f"SPUM 五行偏离(均值20):",
        *dev_lines,
        f"",
        f"大运排盘:",
        *(dayun_lines or ["  (无大运数据)"]),
        f"",
        f"当前大运: {current_dayun.get('gan','')}{current_dayun.get('zhi','') or '(无)'}",
        f"",
        f"出生地: {birth_province or '(未填)'}{' ' + birth_city if birth_city else ''}",
        f"地缘因子: {geo_hint.get('note', '未填')}",
        f"地缘修正方向: {geo_hint.get('correction', {})}",
    ]

    prompt_lines += [
        "",
        "═══════════════════════════════════════════════════════════",
        "## 输出格式：严格 JSON，每段一个 markdown 字符串",
        "═══════════════════════════════════════════════════════════",
        "",
        "输出 JSON（每段是完整的 markdown 文本，不是标签数组）：",
        '{',
        '  "constitution_summary": "5-10字体质总纲（如：水木通明·寒水无火）",',
        '  "sections": {',
        '    "bazi_analysis": "第一段完整 markdown 文本（八字排盘+四柱+五行统计+格局判定）",',
        '    "innate_base": "第二段完整 markdown 文本（先天基底推估）",',
        '    "geo_factor": "第三段完整 markdown 文本（地缘因子修正）",',
        '    "name_career": "第四段完整 markdown 文本（姓名与职业因子）",',
        '    "dayun_current": "第五段完整 markdown 文本（大运排盘+当前大运分析）",',
        '    "constitution_summary_detail": "第六段完整 markdown 文本（体质总纲+核心特征+各系统倾向）"',
        '  }',
        '}',
        "",
        "⚠️ 注意：每个 section 的值是完整的 markdown 段落，里面可以包含表格、列表、加粗等格式。",
        "⚠️ 每个 section 长度建议 150-300 字（第六段可以更长 300-500 字）。",
    ]

    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": settings.DEEPSEEK_MODEL or "deepseek-chat",
                "messages": [{"role": "system", "content": "你是青囊健康的中医体质分析师，输出专业、深刻、有洞察力。禁止建议、禁止恐吓、禁止将来时。每段必须包含至少 1 条天生优势的正向描述。"},
                            {"role": "user", "content": "\n".join(prompt_lines)}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
        )
        if r.status_code != 200:
            return None
        try:
            content = r.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            # 兼容：如果返回的是旧格式（tag_texts/age_desc），降级处理
            if "sections" not in result and "constitution_summary" in result:
                return {
                    "constitution_summary": result["constitution_summary"],
                    "sections": {
                        "bazi_analysis": "",
                        "innate_base": result.get("day_master_note", ""),
                        "geo_factor": "",
                        "name_career": "",
                        "dayun_current": "",
                        "constitution_summary_detail": "",
                    }
                }
            return result
        except Exception:
            return None

