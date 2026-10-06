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
    # ⭐ 缓存 key 加 provider（不同 provider 分开缓存）
    _prov_tag = provider or "default"

    # ── 1. 先查缓存 ──
    cached = _read_cache(qingnang_id, today, v_hash, _prov_tag, meta_hash=meta_h)
    if cached is not None:
        logger.info(f"[notifications] lifestyle cache HIT for {qingnang_id} prov={_prov_tag}")
        return cached

    # ── 2. 缓存未命中 → 调 LLM ──
    logger.info(f"[notifications] lifestyle cache MISS for {qingnang_id} prov={_prov_tag}, calling qingmeng-engine...")
    payload = {"v_base": v_base, "v_current": v_current or v_base}
    # ⭐ 带 city + provider + user_meta（年龄/慢性病/过敏）
    if city:
        payload["city"] = city
    if provider:
        payload["provider"] = provider
    if user_meta:
        payload["user_meta"] = user_meta
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{settings.QINGMENG_URL}/v1/reasoning/lifestyle",
                json=payload,
            )
            if r.status_code == 200:
                data = r.json()
                logger.info(f"[notifications] qingmeng-engine lifestyle OK, engine={data.get('engine')}")
                # ── 3. LLM 成功 → 写缓存（带 meta_hash）──
                _write_cache(qingnang_id, today, v_hash, data, _prov_tag, meta_hash=meta_h)
                return data
            else:
                logger.warning(f"[notifications] qingmeng-engine lifestyle HTTP {r.status_code}")
    except Exception as e:
        logger.warning(f"[notifications] qingmeng-engine lifestyle 不可达: {e}")

    # qingmeng-engine 不可达 → 返回空结构（前端优雅降级）
    return {
        "anchor": {"state": "离线模式", "yi": "养生", "ji": "辛辣"},
        "timeline": [], "cloth_reminders": [], "food_good": [],
        "food_bad": [], "home_reminders": [],
        "absolute_avoid": [], "relative_avoid": [],
        "engine": "backend_fallback",
    }


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
