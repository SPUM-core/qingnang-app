"""life_signal_extractor — 从用户对话里提取结构化生活信号

设计原则：
1. 纯规则引擎（正则 + 关键词组配），不调 LLM
2. 低误报：每个标签至少 2 个独立关键词命中才触发
3. 可扩展：新维度 → 在 _DIMENSION_RULES 里加条目即可
4. 幂等：同一条消息重复抽不会重复插库（靠 source_id 去重）
"""
import re
from dataclasses import dataclass


@dataclass
class SignalHit:
    tag: str            # 维度 tag （bowel / sweat / sleep ...）
    label: str          # 归一化标签
    raw_snippet: str    # 原始匹配片段
    matched_keywords: list


# ═══════════════════════════════════════════════════════
# 规则表：一个维度 = 多个 label 规则
# 每条 label 规则 = 一个 label 名 + 多个触发短语（任意命中即可）
# 短语是 tuple：(正则模式, 或 简单字符串)
# ═══════════════════════════════════════════════════════
_DIMENSION_RULES: dict[str, list[tuple[str, list]]] = {
    # ── 二便 ──
    "bowel": [
        ("便秘",          [r"便秘", r"大便.*干", r"大便.*硬", r"排便.*困难", r"拉不出"]),
        ("便稀",          [r"大便.*稀", r"便.*稀", r"腹泻", r"拉肚子", r"水样便"]),
        ("无便意",        [r"没有便意", r"没便意", r"少便意", r"早上没便意", r"排便少", r"便意.*少"]),
        ("便少",          [r"大便.*少", r"排便.*少", r"拉.*很少"]),
        ("便多",          [r"大便.*多", r"一天.*几次.*大便"]),
        ("便血",          [r"便血", r"大便.*血", r"血便"]),
        ("便秘交替便稀",  [r"便秘.*腹泻|腹泻.*便秘"]),
    ],

    # ── 汗液 ──
    "sweat": [
        ("动则多汗",      [r"一动就出汗", r"稍微动就出汗", r"走两步就出汗", r"一动就满头"]),
        ("自汗",          [r"没动.*出汗", r"不动也出汗", r"自汗"]),
        ("盗汗",          [r"夜间出汗", r"睡着.*出汗", r"睡醒.*一身汗", r"盗汗"]),
        ("全身汗多",      [r"一天.*换.*套.*衣服", r"衣服.*湿", r"汗特别多", r"汗多"]),
        ("局部汗多",      [r"手心.*汗", r"脚心.*汗", r"腋下.*汗"]),
    ],

    # ── 睡眠 ──
    "sleep": [
        ("入睡困难",      [r"睡不着", r"难入睡", r"躺下.*很久.*睡着", r"入睡困难"]),
        ("眠浅易醒",      [r"容易醒", r"眠浅", r"半夜.*醒", r"睡不沉"]),
        ("多梦",          [r"梦多", r"很多梦", r"做.*怪梦"]),
        ("早醒",          [r"早醒", r"天没亮.*醒", r"凌晨.*醒"]),
        ("睡眠不足",      [r"睡不够", r"睡.*小时.*不够", r"熬夜"]),
        ("嗜睡",          [r"特别能睡", r"总想睡", r"睡不醒", r"嗜睡"]),
    ],

    # ── 食欲 ──
    "appetite": [
        ("食欲不振",      [r"没胃口", r"吃不下", r"食欲不振", r"不想吃"]),
        ("易饿",          [r"容易饿", r"饿得快", r"刚吃完.*又饿"]),
        ("反酸",          [r"反酸", r"烧心", r"打嗝.*酸"]),
        ("腹胀",          [r"肚子胀", r"脘腹胀", r"吃完.*胀", r"腹胀"]),
        ("口苦",          [r"口苦", r"嘴里.*苦"]),
        ("口粘",          [r"口粘", r"嘴里.*粘"]),
    ],

    # ── 月经 ──
    "menses": [
        ("量少",          [r"月经量.*少", r"经量.*少", r"姨妈.*少", r"点滴"]),
        ("推迟",          [r"月经.*推迟", r"月经.*延后", r"月经.*延迟", r"月经.*晚",
                           r"姨妈.*推迟", r"姨妈.*延后", r"姨妈.*延迟", r"姨妈.*晚",
                           r"迟迟不来", r"老是.*不来"]),
        ("提前",          [r"提前", r"提前.*来"]),
        ("痛经",          [r"痛经", r"月经.*痛", r"姨妈.*痛", r"腹痛.*月经"]),
        ("闭经",          [r"闭经", r"不来月经", r"半年.*没来"]),
        ("淋漓不尽",      [r"淋漓", r"不干净", r"拖.*十几天"]),
    ],

    # ── 情绪 ──
    "mood": [
        ("焦虑",          [r"焦虑", r"紧张", r"担心", r"怕.*出事"]),
        ("易怒",          [r"容易发火", r"急躁", r"易怒", r"脾气.*大"]),
        ("低落",          [r"情绪.*低", r"提不起劲", r"不开心", r"低落", r"抑郁"]),
        ("叹气",          [r"叹气", r"总是.*叹气"]),
        ("烦躁",          [r"烦躁", r"心烦"]),
    ],

    # ── 体力 ──
    "energy": [
        ("易疲乏",        [r"容易累", r"很容易累", r"走两步.*累", r"疲乏", r"没力气"]),
        ("精力充沛",      [r"精力好", r"精神好", r"不累"]),
        ("腰膝酸软",      [r"腰膝酸软", r"腰酸", r"腿软", r"腰.*酸"]),
        ("手脚发凉",      [r"手脚.*凉", r"怕冷", r"手脚冰凉"]),
        ("手脚发热",      [r"手脚.*热", r"手心.*热", r"脚.*心.*热"]),
    ],

    # ── 饮水 ──
    "thirst": [
        ("口渴",          [r"总是口渴", r"很容易渴", r"一直.*喝水"]),
        ("不喜水",        [r"不渴", r"不想喝水"]),
        ("喜热饮",        [r"喝热", r"喜欢.*热饮"]),
        ("喜冷饮",        [r"喝冰", r"喜欢.*冷", r"爱喝.*凉"]),
    ],

    # ── 皮肤 ──
    "skin": [
        ("皮肤干燥",      [r"皮肤.*干", r"脱屑", r"干皮"]),
        ("皮肤出油",      [r"皮肤.*油", r"出油多"]),
        ("长痘",          [r"长痘", r"痘痘", r"痤疮"]),
        ("过敏",          [r"过敏", r"痒"]),
        ("皮肤黄",        [r"皮肤.*黄", r"面色.*黄"]),
    ],

    # ── 呼吸 ──
    "breath": [
        ("气短",          [r"气短", r"胸闷", r"喘不过气"]),
        ("咳嗽",          [r"咳嗽", r"干咳", r"咳痰"]),
        ("鼻塞",          [r"鼻塞", r"流鼻涕"]),
        ("咽痒",          [r"喉咙.*痒", r"咽.*痒", r"嗓子.*痒"]),
    ],
}


def extract_signals(text: str) -> list[SignalHit]:
    """从一段用户输入文本里提取所有 LifeSignal 命中

    Returns:
        list[SignalHit] — 每条是一个 (tag, label, raw_snippet, matched_keywords)
        同一段 raw_text 里多次匹配同一 label 合并成一条
    """
    if not text or not text.strip():
        return []

    hits: list[SignalHit] = []
    seen: set[tuple] = set()  # (tag, label) 去重

    for tag, rules in _DIMENSION_RULES.items():
        for label, patterns in rules:
            matched_kws = []
            for pat in patterns:
                if isinstance(pat, str):
                    if re.search(pat, text):
                        matched_kws.append(pat)
                elif isinstance(pat, tuple) and pat[0] == "kw":
                    kw = pat[1]
                    if kw in text:
                        matched_kws.append(kw)
            # 命中 ≥2 个独立关键词 → 记为该 label 命中（2026-10-02 修复：原代码 1 个即触发，
            # 与 docstring 承诺的"至少 2 个关键词命中才触发"不符，低误报承诺未兑现）
            if len(matched_kws) >= 2 and (tag, label) not in seen:
                # 从原文里截取匹配片段（截取前后各 10 字）
                first_kw = matched_kws[0]
                m = re.search(re.escape(first_kw), text)
                snippet = ""
                if m:
                    start = max(0, m.start() - 10)
                    end = min(len(text), m.end() + 10)
                    snippet = text[start:end].replace("\n", " ")
                else:
                    snippet = text[:40].replace("\n", " ")

                hits.append(SignalHit(
                    tag=tag, label=label,
                    raw_snippet=snippet,
                    matched_keywords=matched_kws,
                ))
                seen.add((tag, label))

    return hits


def signals_to_dict_list(hits: list[SignalHit]) -> list[dict]:
    """把 SignalHit 列表转成可直接 LifeSignal(**) 的 dict 列表"""
    return [
        {
            "tag": h.tag,
            "label": h.label,
            "raw_text": h.raw_snippet,
            "confidence": {"rule": "keyword", "match": h.matched_keywords},
        }
        for h in hits
    ]


# ═══════════════════════════════════════════════════════
# 测试入口：python -m app.utils.life_signal_extractor
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    sample = "最近早上排便少了、没什么便意。汗多 一动就出汗。一天要换三套衣服。平时月经量极少，延迟。"
    print(f"输入：{sample}\n")
    hits = extract_signals(sample)
    for h in hits:
        print(f"  [{h.tag}] {h.label}  ← {h.matched_keywords}")
