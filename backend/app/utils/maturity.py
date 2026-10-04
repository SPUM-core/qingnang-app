"""maturity - 用户数字模型成熟度四阶段计算

纯函数，基于现有 DB 数据信号权重积分：
  Stage 1 娱乐级  score < 3        → 节气宜忌、心情陪伴、通用健康常识
  Stage 2 食疗级  3 ≤ score < 5    → 试探性食疗 + 穿衣颜色建议
  Stage 3 调理级  5 ≤ score < 8    → 衣食住行全方位 ΔS 调理
  Stage 4 方剂级  score ≥ 8 AND is_member → 方剂推荐（隐藏/会员功能）

设计原则：
  - 纯派生（computed），不在 User 表存 stage 字段，避免漂移
  - 单入口函数 compute_maturity(user, db)，assistant.py / me 端点共用
  - missing_signals 告诉前端"差什么能升级"，引导用户完成更多数据采集
  - 阶段只升不降——即使某次 PPG 信号消失（如设备没连），已建立的信任不回退
"""

from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from ..models import User, Case, Observation, InquirySession, LifeSignal


# ═══════════════════════════════════════════════════════════
# 阶段定义
# ═══════════════════════════════════════════════════════════

STAGE_DEFS = {
    1: {
        "name": "娱乐级",
        "label": "认识你",
        "icon": "🌱",
        "desc": "我们刚刚认识～先聊聊你的生活习惯，慢慢熟悉了再给你更好的建议。",
        "allowed_content": ["节气宜忌", "四季养生常识", "心情陪伴", "通用健康知识"],
        "forbidden_content": ["食疗建议", "穿搭推荐", "作息调整", "方剂"],
        "llm_constraint": (
            "【数字模型成熟度：Stage 1 娱乐级】\n"
            "你对用户的了解还很少——只有基本信息。请只聊：节气宜忌、四季养生常识、"
            "心情陪伴、通用健康知识。不要给具体的食疗、穿搭、作息调整建议。"
            "用朋友聊天的语气，温暖而有分寸。"
        ),
    },
    2: {
        "name": "食疗级",
        "label": "试探性调养",
        "icon": "🍜",
        "desc": "已经认识了，先从饮食和穿着入手——给你一些温和的试探性建议。",
        "allowed_content": ["试探性食疗", "穿衣颜色建议", "节气养护"],
        "forbidden_content": ["作息调整", "家居方位", "方剂"],
        "llm_constraint": (
            "【数字模型成熟度：Stage 2 食疗级】\n"
            "你对用户有基本了解（已建档 + 至少 1 次脉搏采集）。可以给试探性的食疗建议"
            "（如'可以试试山药粥'）和穿衣颜色建议。但不要给作息调整、家居方位或方剂。"
            "保持温和试探的语气，像朋友的生活分享，不是专业指导。"
        ),
    },
    3: {
        "name": "调理级",
        "label": "全方位调理",
        "icon": "🏠",
        "desc": "数据收集足够了，让我从饮食、穿搭、作息、家居方位全方位调理你的生活节奏。",
        "allowed_content": ["食疗", "穿搭", "作息调整", "家居方位", "时辰养生"],
        "forbidden_content": ["方剂（需会员）"],
        "llm_constraint": (
            "【数字模型成熟度：Stage 3 调理级】\n"
            "你对用户有充分了解（多次脉搏采集 + 问诊完成）。可以给出饮食、穿搭、作息、"
            "家居方位、时辰养生的全方位调理建议。这些建议基于用户的五形向量偏移，"
            "是定制化的生活调整方案。语气专业但温暖，让用户觉得'这说的就是我'。"
            "注意：不要给方剂/处方/药材建议——这需要会员权限。"
        ),
    },
    4: {
        "name": "方剂级",
        "label": "深层调平",
        "icon": "⚗️",
        "desc": "会员功能：基于充分的数字模型，提供方剂级调理方案（隐藏功能，不在公开说明中提及）。",
        "allowed_content": ["全部（含方剂）"],
        "forbidden_content": [],
        "llm_constraint": (
            "【数字模型成熟度：Stage 4 方剂级 · 会员功能】\n"
            "你对用户有成熟了解。可以给出包括方剂在内的深层调平方案。"
            "方剂建议基于用户的五形向量和长期体质偏移，是君臣佐使结构的完整方案。"
            "但注意合规措辞：不说'处方'、'用药'，说'调平方案'、'食材/道地药材组合'。"
        ),
    },
}


def compute_maturity(user: User, db: Session) -> dict:
    """计算用户数字模型成熟度。

    Returns dict:
      { stage: 1-4, name, label, icon, desc, allowed_content, forbidden_content,
        score: int, details: dict, missing_signals: list[str], next_target: str,
        is_member: bool }
    """
    details: dict = {}
    score = 0

    # ── 信号 1：基本资料完整度（4 项，各 1 分）──
    profile_items = {
        "height": user.height is not None,
        "weight": user.weight is not None,
        "birth_date": bool(user.birth_date),
        "birth_hour": bool(user.birth_hour),
    }
    profile_score = sum(1 for v in profile_items.values() if v)
    details["profile"] = profile_items
    details["profile_score"] = profile_score
    score += profile_score

    # ── 信号 2：Case 存在 + v_baseline 存在（2 分）──
    case = db.query(Case).filter(Case.user_id == user.id).first()
    details["case_exists"] = case is not None
    has_baseline = bool(case and case.v_baseline)
    details["has_baseline"] = has_baseline
    has_observation = bool(case and case.v_current)
    details["has_observation"] = has_observation
    if case:
        score += 2
    elif has_baseline:
        score += 1  # 有 v_baseline 但 Case 刚在创建中

    # ── 信号 3：PPG 观测次数（0 次 0 分 / ≥1 +1 / ≥3 +1 / ≥5 +1）──
    obs_count = 0
    if case:
        obs_count = db.query(Observation).filter(
            Observation.case_id == case.id
        ).count()
    details["observation_count"] = obs_count
    if obs_count >= 1:
        score += 1
    if obs_count >= 3:
        score += 1
    if obs_count >= 5:
        score += 1

    # ── 信号 4：问诊完成（2 分）──
    inquiry = db.query(InquirySession).filter(
        InquirySession.user_id == user.id,
        InquirySession.status == "completed",
    ).order_by(InquirySession.completed_at.desc()).first()
    details["inquiry_completed"] = inquiry is not None
    details["inquiry_stage"] = inquiry.stage if inquiry else None
    if inquiry:
        score += 2

    # ── 信号 5：LifeSignal 不同 tag 数（≥3 +1 / ≥5 +1）──
    tag_count = 0
    if case or user.id:
        tag_count = db.query(func.count(func.distinct(LifeSignal.tag))).filter(
            LifeSignal.user_id == user.id,
        ).scalar() or 0
    details["signal_tag_count"] = tag_count
    if tag_count >= 3:
        score += 1
    if tag_count >= 5:
        score += 1

    # ── is_member（手动标记，未来可接会员系统）──
    # 暂时用 is_doctor 或 dev_seed 标记替代——真实会员功能接入后替换
    is_member = bool(getattr(user, "is_member", False)) or bool(user.is_doctor)
    details["is_member"] = is_member

    # ═══ 阈值映射 ═══
    if score >= 8 and is_member:
        stage = 4
    elif score >= 5:
        stage = 3
    elif score >= 3:
        stage = 2
    else:
        stage = 1

    # ═══ missing_signals：告诉前端差什么能升级 ═══
    missing: list[str] = []

    def _profile_missing():
        keys = [k for k, v in profile_items.items() if not v]
        labels = {"height": "身高", "weight": "体重", "birth_date": "出生日期", "birth_hour": "出生时辰"}
        return [labels[k] for k in keys]

    if stage == 1:
        missing += _profile_missing()
        if not case:
            missing.append("完成数字模型建档")
        elif not has_baseline:
            missing.append("做第一次脉搏采集建立基线")
        next_target = "完成建档 + 第一次脉搏采集 → 进入食疗级"
    elif stage == 2:
        if obs_count < 3:
            missing.append(f"再做 {3 - obs_count} 次脉搏采集")
        if not inquiry:
            missing.append("完成一次深度问诊")
        next_target = "3 次脉搏 + 问诊完成 → 进入调理级"
    elif stage == 3:
        if not is_member:
            missing.append("开通会员解锁深层调平方案")
        next_target = "开通会员 → 进入方剂级（深层调平）"
    else:
        next_target = "已达最高阶段"

    # ═══ 返回 ═══
    stage_def = STAGE_DEFS[stage]
    return {
        "stage": stage,
        "name": stage_def["name"],
        "label": stage_def["label"],
        "icon": stage_def["icon"],
        "desc": stage_def["desc"],
        "allowed_content": stage_def["allowed_content"],
        "forbidden_content": stage_def["forbidden_content"],
        "llm_constraint": stage_def["llm_constraint"],
        "score": score,
        "max_score": 11,  # 满分（4+2+3+2+2=11）
        "details": details,
        "missing_signals": missing,
        "next_target": next_target,
        "is_member": is_member,
    }
