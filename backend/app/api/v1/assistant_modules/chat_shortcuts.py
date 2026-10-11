"""chat_shortcuts - 高频结构化问题捷径：daily_brief 数据直接拼自然语言回答（绕过 LLM）"""
# ═══════════════════════════════════════════════════════
# 高频结构化问题 — 引擎直接返回，绕过 LLM
# ═══════════════════════════════════════════════════════

def _intent_shortcut(message: str, brief: dict | None, stage: int = 1) -> str | None:
    """检测高频结构化问题，用 daily_brief 数据直接拼自然语言回答。

    Stage 守卫（关键）：
      Stage 1 → 只放行日期/干支类（节气宜忌），屏蔽食物/颜色/宜忌
      Stage 2+ → 全部放行

    返回 None = 不是高频问题 OR 阶段不允许（走 LLM 路径，那里有 stage constraint 注入）
    返回 str = 引擎直接生成的回答（零延迟，确定性）
    """
    if not brief or not message:
        return None

    msg = message.lower()

    # ── Stage 1 守卫：只放节气/干支/日期，屏蔽食物/颜色/宜忌 ──
    if stage == 1:
        # 仅干支/日期/节气类关键词放行
        if not any(k in msg for k in ("干支", "今天几号", "今天什么日", "今日干支", "节气")):
            return None  # 走 LLM，那里有 stage 约束注入
        # 但也要检查 stage 1 禁止的类别
        if any(k in msg for k in ("吃什么", "饮食", "食物", "颜色", "穿什么", "宜忌", "宜什么", "宜")):
            return None

    # ── Stage 2+：正常处理所有类别 ──

    # ── 颜色/穿搭类 ──
    if any(k in msg for k in ("颜色", "穿什么", "配饰", "穿搭", "衣服", "好看")):
        cloth = brief.get("cloth", [])
        if not cloth:
            return None
        lines = []
        cloth_ok = [c for c in cloth if "宜穿" in c["title"]]
        cloth_bad = [c for c in cloth if c["title"].startswith("避免") or "忌" in c["title"]]
        accessories = [c for c in cloth if "配饰" in c["title"]]

        if cloth_ok:
            colors = [c["title"].replace("宜穿：", "").replace("色系", "") for c in cloth_ok]
            lines.append("根据你的 SPUM 状态，推荐你试试 %s。" % "、".join(colors))
            for c in cloth_ok[:2]:
                lines.append("  · %s —— %s" % (c["title"], c["desc"]))
        if accessories:
            for a in accessories:
                lines.append("另外，%s。" % a["desc"])
        if cloth_bad:
            lines.append("要注意 %s。" % "、".join(c["title"] for c in cloth_bad[:2]))
        return "\n".join(lines)

    # ── 食物/饮食类 ──
    if any(k in msg for k in ("吃什么", "饮食", "食物", "推荐吃", "今天吃", "食谱", "早餐", "午餐", "晚餐")):
        fg = brief.get("food_good", [])
        fb = brief.get("food_bad", [])
        if not fg and not fb:
            return None
        lines = []
        anchor = brief.get("anchor", {})
        state = anchor.get("state", "")
        if state and state != "调和":
            lines.append("你当前状态偏 %s，" % state)

        if fg:
            lines.append("今天推荐 %s。" % "、".join(f["title"] for f in fg))
            for f in fg[:3]:
                lines.append("  · %s —— %s" % (f["title"], f["desc"]))
        if fb:
            lines.append("这些尽量别碰：%s。" % "、".join(f["title"] for f in fb))
        return "\n".join(lines)

    # ── 宜忌/今日类 ──
    if any(k in msg for k in ("宜忌", "宜什么", "忌什么", "今天注意", "今天宜", "今天忌", "今天适合", "今日宜忌")):
        anchor = brief.get("anchor", {})
        if not anchor:
            return None
        lines = []
        gz = anchor.get("ganzhi", "")
        if gz:
            line = "今天是 %s 日" % gz
            if anchor.get("chong"):
                line += "，冲 %s" % anchor["chong"]
            lines.append(line + "。")
        if anchor.get("yi"):
            lines.append("宜：%s。" % anchor["yi"])
        if anchor.get("ji"):
            lines.append("忌：%s。" % anchor["ji"])
        state = anchor.get("state", "")
        if state and state != "调和":
            lines.append("你当前状态：%s。" % state)
        return "\n".join(lines)

    # ── 干支/日期类 ──
    if any(k in msg for k in ("干支", "今天几号", "今天什么日", "今日干支")):
        anchor = brief.get("anchor", {})
        if not anchor or not anchor.get("ganzhi"):
            return None
        gz = anchor["ganzhi"]
        line = "今天是 %s" % gz
        if anchor.get("chong"):
            line += "，冲 %s" % anchor["chong"]
        line += "。"
        return line

    return None  # 不匹配任何高频 intent → 走 LLM


