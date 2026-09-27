"""knowledge - 知识库（通用养生内容 + 用户 v_base 个性化推荐）"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import User, Case
from ..deps import get_current_user

router = APIRouter()

# 通用知识卡片（非胡运涛案例）
GENERAL_ITEMS = [
    {"id": "v1", "type": "video", "title": "子午流注与入睡节律",
     "summary": "子时(23-1点)水形主令，是载流体自然降温窗口。熬夜为什么伤肾水形。",
     "duration": "05:23", "author": "青囊中医", "source": "内部",
     "tags": ["睡眠", "子午流注", "水形"],
     "url": ""},
    {"id": "v2", "type": "video", "title": "戌时泡脚的三个关键",
     "summary": "水温、时长、加什么——温土潜火的最佳时辰。",
     "duration": "03:12", "author": "青囊中医", "source": "内部",
     "tags": ["泡脚", "土形", "时辰"],
     "url": ""},
    {"id": "a1", "type": "article", "title": "五形偏弱形的日常食补原则",
     "summary": "木弱疏气、火弱养阳、土弱温补、金弱润肺、水弱滋肾。",
     "author": "青囊中医", "source": "内部",
     "tags": ["食疗", "五形"],
     "url": ""},
    {"id": "a2", "type": "article", "title": "为什么你的 PPG 信号不稳定？",
     "summary": "手指压力、呼吸节律、环境震动——影响 CheezPPG 读数的常见因素。",
     "author": "青囊研发", "source": "内部",
     "tags": ["PPG", "观测质量"],
     "url": ""},
    {"id": "p1", "type": "podcast", "title": "晨间 5 分钟：温淡盐水的正确喝法",
     "summary": "一杯水、一勺盐、空腹、慢慢喝——唤醒载流体循环。",
     "author": "青囊陪伴", "source": "内部",
     "tags": ["晨间", "水形"],
     "url": ""},
]


@router.get("/")
def list_knowledge(db: Session = Depends(get_db),
                   current: User = Depends(get_current_user),
                   keyword: str = "",
                   tag: str = "",
                   limit: int = 30):
    """知识库列表 — 通用卡片 + 用户 v_base 个性化推荐"""
    items = [dict(it) for it in GENERAL_ITEMS]

    # 个性化：根据用户 v_base 打 personalized / reason 标签
    v = current.v_base or {}
    case = db.query(Case).filter(Case.user_id == current.id).first()
    if case and case.v_baseline:
        v = case.v_baseline

    label = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}
    weak = [label[k] for k, val in v.items() if isinstance(val, (int, float)) and val < 45]
    strong = [label[k] for k, val in v.items() if isinstance(val, (int, float)) and val > 65]

    for it in items:
        it["personalized"] = any(
            t in it["tags"] for t in [
                {"木": "木", "火": "火", "土": "土", "金": "金", "水": "水"}.get(w, "")
                for w in weak
            ] if t
        )
        if it["personalized"]:
            it["reason"] = f"你的{weak[0]}形偏弱"

    # 关键词过滤
    if keyword:
        kw = keyword.lower()
        items = [it for it in items if kw in it["title"].lower()
                 or kw in it["summary"].lower()
                 or any(kw in t.lower() for t in it.get("tags", []))]
    if tag:
        items = [it for it in items if tag in it.get("tags", [])]

    # 个性化置顶
    items.sort(key=lambda it: (0 if it["personalized"] else 1, it["id"]))

    return {"items": items[:limit], "total": len(items)}
