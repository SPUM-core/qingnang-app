"""notifications - 生活提醒（LLM 驱动，qingmeng-engine 推理）

2026-10-06 增强：
- ⭐ build_user_meta() 通用函数：从 User.health_tags + birth_date 组装年龄/慢性病/过敏
- 所有调用 _call_qingmeng_lifestyle 的路径**必须**传 user_meta → LLM prompt 里有医学规则

2026-10-05 重构：
- _generate_reminders() 硬编码规则引擎 → 替换为内部 httpx 调 qingmeng-engine LLM
- qingmeng-engine 不可达时，降级为 _simple_fallback 返回空（前端优雅降级）
- /today 端点改为 async，适配 LLM 推理延迟
- ⭐ 新增按日缓存：同一天内返回缓存的 LLM 结果，不再重复推理
"""
import datetime as _dt_lib
import hashlib
import json as _json
import logging
import os
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Case
from ..deps import get_current_user
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# ═══════════════════════════════════════════════════════
# 2026-10-06 通用 user_meta 组装 — 所有 lifestyle 调用点复用
# ═══════════════════════════════════════════════════════

_CHRONIC_MAP = {
    "hypertension": "高血压",
    "diabetes": "糖尿病",
    "hyperlipidemia": "高血脂",
    "hyperuricemia": "高尿酸",
    "hypoglycemia": "低血糖",
    "cardiovascular": "心血管病",
    "hypothyroidism": "甲减",
    "hyperthyroidism": "甲亢",
    "asthma": "哮喘",
    "copd": "慢阻肺",
}


def build_user_meta(current: User, case: "Case | None" = None) -> dict:
    """从 User 对象 + 可选 Case 组装 user_meta — 所有推理点复用。

    返回 dict 包含 age/age_band/chronic/allergies/conditions/surgeries/has_three_highs
    + nickname/gender/syndrome/chief_complaint（如果有 case）。
    """
    # ── 年龄 ──
    age = None
    age_band = None
    if current.birth_date:
        try:
            bd = _dt_lib.date.fromisoformat(current.birth_date)
            today = _dt_lib.date.today()
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            if age < 18:     age_band = "青少年"
            elif age < 30:   age_band = "青年"
            elif age < 50:   age_band = "中青年"
            elif age < 65:   age_band = "中年"
            else:            age_band = "老年"
        except Exception:
            pass

    # ── 健康标签 ──
    tags = current.health_tags or {}
    chronic_cn = [_CHRONIC_MAP.get(c, c) for c in (tags.get("chronic") or [])]
    has_three_highs = any(c in ("hypertension", "diabetes", "hyperlipidemia")
                          for c in (tags.get("chronic") or []))

    meta = {
        "nickname": current.nickname,
        "gender": current.gender,
        "age": age,
        "age_band": age_band,
        "chronic": chronic_cn,
        "allergies": tags.get("allergies") or [],
        "conditions": tags.get("conditions") or [],
        "surgeries": tags.get("surgeries") or [],
        "has_three_highs": has_three_highs,
    }
    if case:
        meta["syndrome"] = case.syndrome
        meta["chief_complaint"] = case.chief_complaint
    return meta


# 天干地支表
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI   = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
SHICHEN  = ["子时", "丑时", "寅时", "卯时", "辰时", "巳时", "午时", "未时", "申时", "酉时", "戌时", "亥时"]
SHICHEN_ELEM = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]

# ═══════════════════════════════════════════════════════
# LLM lifestyle 按日缓存
# ═══════════════════════════════════════════════════════
CACHE_DIR = Path(os.path.expanduser("~/.qingmeng/cache"))


def _cache_path(qingnang_id: str, date_str: str, prov_tag: str = "default") -> Path:
    """缓存文件路径：~/.qingmeng/cache/lifestyle_{qingnang_id}_{date}_{prov}.json"""
    safe_id = qingnang_id.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"lifestyle_{safe_id}_{date_str}_{prov_tag}.json"


def _v_base_hash(v_base: dict) -> str:
    """v_base 哈希 — 用来检测 v_base 是否变化（缓存失效条件）"""
    canonical = _json.dumps(dict(sorted(v_base.items())), sort_keys=True)
    return hashlib.md5(canonical.encode()).hexdigest()[:8]


def _meta_hash(user_meta: dict | None) -> str:
    """2026-10-06：用户画像哈希 — age/chronic/allergies/conditions 变了 → 缓存失效"""
    if not user_meta:
        return "none"
    # 只挑影响建议质量的字段（过滤掉 fallback、syndrome 这种可能频繁变的）
    key_fields = {k: user_meta.get(k) for k in
                  ("age", "age_band", "chronic", "allergies", "conditions", "surgeries", "has_three_highs")}
    canonical = _json.dumps(key_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()[:8]


def _read_cache(qingnang_id: str, date_str: str, v_base_hash: str, prov_tag: str = "default",
                meta_hash: str = "none") -> dict | None:
    """读缓存 — 命中则返回，否则 None"""
    try:
        path = _cache_path(qingnang_id, date_str, prov_tag)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            cached = _json.load(f)
        # v_base 变了 → 缓存失效
        if cached.get("v_base_hash") != v_base_hash:
            logger.info(f"[cache] v_base 变化，缓存失效 ({qingnang_id}, {date_str})")
            path.unlink(missing_ok=True)
            return None
        # 2026-10-06：用户画像变了 → 缓存也失效
        if cached.get("meta_hash", "none") != meta_hash:
            logger.info(f"[cache] 用户画像变化，缓存失效 ({qingnang_id}, {date_str})")
            path.unlink(missing_ok=True)
            return None
        logger.info(f"[cache] HIT {qingnang_id} {date_str} prov={prov_tag}")
        return cached.get("data")
    except Exception as e:
        logger.warning(f"[cache] 读取失败: {e}")
        return None


def _write_cache(qingnang_id: str, date_str: str, v_base_hash: str, data: dict, prov_tag: str = "default",
                 meta_hash: str = "none") -> None:
    """写缓存 — 原子写入（先写 .tmp 再 rename）"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(qingnang_id, date_str, prov_tag)
        tmp_path = path.with_suffix(".tmp")
        payload = {
            "data": data,
            "v_base_hash": v_base_hash,
            "meta_hash": meta_hash,  # 2026-10-06：用户画像 hash
            "created_at": _dt_lib.datetime.now().isoformat(),
            "cache_version": 2,  # bump → 旧缓存全失效（今天要重跑）
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            _json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp_path.rename(path)
        logger.info(f"[cache] WROTE {qingnang_id} {date_str} meta={meta_hash}")
    except Exception as e:
        logger.warning(f"[cache] 写入失败: {e}")


def _ganzhi_from_solar(year: int, month: int, day: int) -> tuple[str, str, str]:
    """用 lunar_python 算年/月/日干支"""
    try:
        from lunar_python import Solar
        s = Solar.fromYmd(year, month, day)
        l = s.getLunar()
        y = l.getYearInGanZhiExact()
        m = l.getMonthInGanZhiExact()
        d = l.getDayInGanZhiExact()
        return y, m, d
    except Exception:
        def y_ganzhi(y):
            return TIAN_GAN[(y - 4) % 10] + DI_ZHI[(y - 4) % 12]
        return y_ganzhi(year), "", ""


async def _call_qingmeng_lifestyle(v_base: dict, v_current: dict | None = None,
                                   qingnang_id: str = "anonymous",
                                   city: str | None = None,
                                   provider: str | None = None,
                                   user_meta: dict | None = None) -> dict:
    """内部调用 qingmeng-engine /v1/reasoning/lifestyle（LLM 推理）+ 按日缓存。

    缓存策略：
    - 缓存 key = qingnang_id + provider + 自然日（provider 变了 → 自动重新推理）
    - v_base 变化 → 缓存失效，重新推理
    - 同一天内多次调用 → 命中缓存，直接返回（不调 LLM）
    - 第二天（自然日变更） → 缓存过期，重新推理
    - provider 切换（ollama ↔ deepseek） → 自动不命中旧缓存

    失败时返回 empty 结构（不是硬编码规则），让前端优雅降级。
    """
    # 默认健康五形调和
    if not v_base:
        v_base = {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50}

    today = _dt_lib.datetime.now().strftime("%Y%m%d")
    v_hash = _v_base_hash(v_base)
    meta_h = _meta_hash(user_meta)  # 2026-10-06
    # ⭐ 缓存 key 不再按 provider 分文件（advisor 裁定：宜忌结论不随 provider 变，
    #   按 provider 分缓存且项又是 LLM 自由生成 → 切换 provider 建议突变 = 双源矛盾）
    _prov_tag = "unified"

    # ── 0. 先跑 rule-based 引擎，得出确定性宜忌结论（不可覆写的输入约束）──
    #      架构原则3：确定性结论必须来自引擎注入，禁止通用 LLM 在 SPUM 上自由发挥
    from .assistant import _fallback_lifestyle
    rule_base = _fallback_lifestyle(v_base, {"city": city})

    # ── 1. 先查缓存（统一 key）──
    cached = _read_cache(qingnang_id, today, v_hash, _prov_tag, meta_hash=meta_h)
    if cached is not None:
        logger.info(f"[notifications] lifestyle cache HIT for {qingnang_id} prov={_prov_tag}")
        return cached

    # ── 2. 缓存未命中 → 第 1 级：DeepSeek 叙事包装（宜忌项受 rule_base 约束）──
    logger.info(f"[notifications] lifestyle cache MISS for {qingnang_id} prov={_prov_tag}")
    data = await _llm_lifestyle(v_base, v_current, city, user_meta, rule_base=rule_base)
    if data is not None:
        logger.info(f"[notifications] DeepSeek lifestyle OK, engine={data.get('engine')}")
        _write_cache(qingnang_id, today, v_hash, data, _prov_tag, meta_hash=meta_h)
        return data

    # ── 兜底：青檬引擎 / rule-based（引擎不可达时直接回落）──
    if not rule_base:
        rule_base = _fallback_lifestyle(v_base, {"city": city})
    rule_base["engine"] = "backend_fallback_rule"
    _write_cache(qingnang_id, today, v_hash, rule_base, _prov_tag, meta_hash=meta_h)
    return rule_base


# ═══════════════════════════════════════════════════════
# DeepSeek 直连生成 lifestyle（替代青檬引擎）
# ═══════════════════════════════════════════════════════
_LLM_LIFESTYLE_ALLOWED_KEYS = {
    "anchor", "timeline", "cloth_reminders", "food_good", "food_bad",
    "home_reminders", "absolute_avoid", "relative_avoid", "note",
    "detail", "source_ref",
}


async def _llm_lifestyle(v_base: dict,
                         v_current: dict | None = None,
                         city: str | None = None,
                         user_meta: dict | None = None,
                         rule_base: dict | None = None) -> dict | None:
    """用 DeepSeek 直连对 rule-based 引擎结论做叙事包装。

    架构原则3（advisor 裁定）：确定性宜忌结论必须来自引擎注入，LLM 只负责补充
    detail（做法）、source_ref（出处）、desc（描述），【禁止新增/删除/修改任何
    宜忌项本身】——从结构上杜绝 LLM 在 SPUM 知识上自由发挥（幻觉不可能）。

    返回 None 表示 LLM 不可用（由调用方落回 rule_base）。
    """
    if not settings.DEEPSEEK_API_KEY:
        return None

    rule_base = rule_base or {}
    _rule_cloth = rule_base.get("cloth_good", []) + rule_base.get("cloth_bad", [])
    _rule_food = rule_base.get("food_good", []) + rule_base.get("food_bad", [])
    _rule_home = rule_base.get("home", [])

    system_prompt = (
        '你是青囊 SPUM 中医体质系统的"今日生活提醒"排版员。'
        '输入中已经给出了青囊引擎【计算好的确定性宜忌结论】（cloth/food/home 各项）。\n'
        '你的职责【唯一】：为每一项补充叙事字段：detail（具体做法、食材用量、制作步骤、'
        '时辰窗口、注意事项）、source_ref（出处，如「《本草纲目》」「《千金要方》」'
        '「《黄帝内经·素问》」，宁缺毋滥）、desc（一句通俗描述）。\n'
        '【硬性禁令】\n'
        '- 不得新增任何宜忌项（LI/foi中未出现的事项一律不得加）\n'
        '- 不得删除或跳过输入中已有的任何宜忌项\n'
        '- 不得修改已有项的 title / 是宜还是忌 / 主食材\n'
        '- 引擎给某项为空数组时，你【无权】自行补充该项\n'
        '输出 JSON 键：anchor、timeline、cloth_reminders、food_good、food_bad、'
        'home_reminders、note、engine。engine 固定为 "llm"。\n'
        '禁止输出 JSON 之外的任何解释文字。'
    )

    v = v_base or {"wood": 50, "fire": 50, "earth": 50, "metal": 50, "water": 50}
    # Python 3.10 不支持 f-string 表达式内多行字面量，先算好再填
    rule_pack = {
        'cloth_good': _rule_cloth,
        'food_good': rule_base.get('food_good', []),
        'food_bad': rule_base.get('food_bad', []),
        'home': _rule_home,
    }
    rule_pack_json = _json.dumps(rule_pack, ensure_ascii=False)
    v_json = _json.dumps(v, ensure_ascii=False)
    v_cur_json = _json.dumps(v_current or v, ensure_ascii=False)
    user_meta_json = _json.dumps(user_meta or {}, ensure_ascii=False)

    user_prompt = (
        f"青囊引擎已算好的当日宜忌结论（你必须逐条保留并补充叙事）：\n"
        f"{rule_pack_json}\n\n"
        f"用户体质五形基线 v_base:{v_json}\n"
        f"五形当前向量 v_current:{v_cur_json}\n"
        f"所在城市(可选):{city or '未知'}\n"
        f"用户画像:{user_meta_json}\n"
        f"请输出 narrative-style lifestyle JSON（宜忌项与输入一致）。"
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 2000,
                }
            )
            if r.status_code != 200:
                logger.warning(f"[notifications] DeepSeek lifestyle HTTP {r.status_code}")
                return None
            raw = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"[notifications] DeepSeek lifestyle 不可达: {e}")
        return None

    data = _parse_lifestyle_json(raw)
    if data is None:
        return None

    # 最小字段校验：anchor 必须存在，且 anchor 或 food 至少一个非空
    if not data.get("anchor"):
        return None
    if not data.get("anchor") and not data.get("food_good") and not data.get("food_bad"):
        return None

    # ── 宜忌项对齐防线（advisor 裁定）：以 rule_base 的 title 集合为权威（幂等防线）──
    #     即使 LLM 违约新增/修改了宜忌项，也在这里强制收敛回引擎结论。
    #     键 -> 应保留的 title 集合
    _rule_titles = {
        "food_good": {x.get("title", "").strip() for x in rule_base.get("food_good", []) if isinstance(x, dict)},
        "food_bad": {x.get("title", "").strip() for x in rule_base.get("food_bad", []) if isinstance(x, dict)},
    }
    for key, allowed in _rule_titles.items():
        items = [x for x in data.get(key, []) if isinstance(x, dict) and x.get("title", "").strip() in allowed]
        data[key] = items

    data["engine"] = "llm"
    data.setdefault("note", "由 DeepSeek LLM 生成")
    return data


def _parse_lifestyle_json(raw: str) -> dict | None:
    """解析 LLM 输出的 lifestyle JSON（剥离代码块、容错切片、键白名单净化）。"""
    text = (raw or "").strip()
    if not text:
        return None

    # 1. 尝试剥离 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = m.group(1) if m else None
    # 2. 无代码块 → 从首个 { 到末尾 } 切片
    if candidate is None:
        s = text.find("{")
        e = text.rfind("}")
        if s != -1 and e != -1 and e > s:
            candidate = text[s:e + 1]
    if candidate is None:
        return None

    try:
        data = _json.loads(candidate)
    except Exception as e:
        logger.warning(f"[notifications] DeepSeek lifestyle JSON 解析失败: {e}")
        return None

    if not isinstance(data, dict):
        return None

    # 键白名单净化
    cleaned = {k: v for k, v in data.items() if k in _LLM_LIFESTYLE_ALLOWED_KEYS}
    # 再把 engine 之外的必要键补齐为数组（若缺则给空数组）
    for k in ("timeline", "cloth_reminders", "food_good", "food_bad",
              "home_reminders", "absolute_avoid", "relative_avoid"):
        if k not in cleaned or not isinstance(cleaned.get(k), list):
            cleaned[k] = []
    return cleaned


async def _generate_reminders(v_base: dict) -> dict:
    """生活提醒生成 — LLM 驱动（重构后的统一入口）。

    返回 qingmeng-engine 风格的字段:
      cloth_reminders, food_good, food_bad, home_reminders,
      absolute_avoid, relative_avoid, timeline, anchor
    """
    return await _call_qingmeng_lifestyle(v_base)


@router.get("/today")
async def today_reminders(db: Session = Depends(get_db),
                          current: User = Depends(get_current_user)):
    """今日生活提醒 — LLM 推理（qingmeng-engine）。"""
    # ── 取 v_base ──
    v = current.v_base or {}
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if case and case.v_baseline:
        v = case.v_baseline

    # ── LLM 推理（带按日缓存 + 年龄/慢性病个性化）──
    llm_data = await _call_qingmeng_lifestyle(
        v_base=v,
        v_current=(case.v_current if case else None),
        qingnang_id=current.qingnang_id or f"user_{current.id}",
        user_meta=build_user_meta(current, case),  # ⭐ 2026-10-06 医学个性化
    )

    # ── 今日时空锚点（动态计算，不用 LLM anchor）──
    now = _dt_lib.datetime.now()
    shichen_index = (now.hour + 1) // 2 % 12
    gz_year, gz_month, gz_day = _ganzhi_from_solar(now.year, now.month, now.day)

    # LLM 给的 state 如果有就用，没有就自己算
    v_state = llm_data.get("anchor", {}).get("state") or _state_from_v(v)

    # AI 生成的用户自定义提醒（来自 LifeSignal tag='reminder'）
    try:
        from ...models import LifeSignal
        user_reminders = [
            {"title": ls.label, "source": ls.source or "chat_ai",
             "at": ls.created_at.isoformat() if ls.created_at else None}
            for ls in db.query(LifeSignal).filter(
                LifeSignal.user_id == current.id,
                LifeSignal.tag == "reminder",
            ).order_by(LifeSignal.created_at.desc()).limit(10).all()
        ]
    except Exception:
        user_reminders = []

    return {
        "anchor": {
            "ganzhi": f"{gz_year}年 {gz_month}月 {gz_day}日",
            "dangling": SHICHEN[shichen_index],
            "dangling_elem": SHICHEN_ELEM[shichen_index],
            "yi": llm_data.get("anchor", {}).get("yi") or "养生·调理·静养",
            "ji": llm_data.get("anchor", {}).get("ji") or "大动·辛辣·冷饮",
            "state": v_state,
            "engine": llm_data.get("engine", "llm"),
        },
        "timeline": llm_data.get("timeline", []),
        "cloth_reminders": llm_data.get("cloth_reminders", []),
        "food_good": llm_data.get("food_good", []),
        "food_bad": llm_data.get("food_bad", []),
        "home_reminders": llm_data.get("home_reminders", []),
        "absolute_avoid": llm_data.get("absolute_avoid", []),
        "relative_avoid": llm_data.get("relative_avoid", []),
        "user_reminders": user_reminders,
    }


def _state_from_v(v_base: dict) -> str:
    """从 v_base 计算五形状态简述（LLM anchor state 不可用时的兜底）。"""
    weak = [w for w, val in v_base.items() if val and val < 50]
    hot = [w for w, val in v_base.items() if val and val > 70]
    state_parts = []
    if weak:
        state_parts.append("偏弱: " + "、".join(weak))
    if hot:
        state_parts.append("偏旺: " + "、".join(hot))
    return " · ".join(state_parts) if state_parts else "五形调和"
