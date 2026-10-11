"""chat_prompt - 系统提示词构建：SPUM 世界观模板 + 用户数字模型注入"""
from sqlalchemy.orm import Session
import time

from ....models import User, Case, Observation, TreatmentPlan
from ....utils.maturity import compute_maturity
from ....utils.wuxing import graph_diagnose as _graph_diagnose
from ....templates import build_response_schema_prompt
from .chat_actions import _EXECUTE_WHITELIST

# ═══════════════════════════════════════════════════════
# System Prompt 构建器 - 注入用户完整数字模型 + 成熟度阶段约束
# ═══════════════════════════════════════════════════════
def build_system_prompt(user: User, db: Session, maturity: dict | None = None) -> str:
    """构建青囊管家 AI 的 System Prompt（2000+ 字完整上下文）

    maturity 预计算可避免重复查询——assistant/chat 路由已预先算好。
    传 None 时内部重新计算。
    """
    if maturity is None:
        maturity = compute_maturity(user, db)

    # ═══════════════════════════════════════════════════════
    # 【核心世界观】SPUM 五形拓扑（替代之前的硬约束枷锁）
    # 五形不是五种元素，是人体关系网络的五种拓扑相位
    # 唯一公理根：关系定义存在（A0）——没有关系就没有存在
    # 五步帧自发生成五种相位：创生/连接/变化体积/判断/删除 → 水/—/火/土/金
    # ═══════════════════════════════════════════════════════
    spum_worldview = f"""
【你的本体论】
你是青囊管家，基于 SPUM（结构化五行统一模型）。你面对的不是一个"病人"，
而是一张正在演化的关系网络——人体是能量关系构成的动态拓扑结构。

【五形是拓扑相位，不是元素】
网络在演化中自然呈现五种结构状态（完备性定理：恰好五个，不多不少）：
  · 水形（传输）：链式结构，能量能否送达远端——对应经络通畅、气血传输
  · 木形（骨架）：闭合环结构，系统的结构性稳定——对应脏腑功能的稳定框架
  · 土形（储备）：松散低度节点构成的冗余池——对应气血储备、可调度能量
  · 金形（修剪）：桥边与可删除目标——对应细胞代谢、旧结构清理与再生
  · 火形（梯度）：密度不均匀产生的定向场，能量流的方向——对应代谢活力、能量分布

五形是重叠的方面，不是互斥的划分。同一节点可以同时属于多个形。
每个形承载的语义不能由其余四个推出——删去任何一个，演化语义就会丢失。

【耦合动力学：从公理自发生成，不是生克关系】
  火形梯度 → 驱动水形链定向输送土形储备 → 土形到木形前沿 → 木形环扩展
  → 环基数 μ 超临界触发木僵 → 金形修剪激活 → 释放节点回归土形
  → 同时产生新的 σ 不均匀 → 火形梯度再生

【人体是折叠晶体——五区域内化的解Ⅳ/解Ⅴ】
人体不是装满器官的容器——是人（解Ⅴ，递归解），继承动物（解Ⅳ，折叠解）的结构：
植物（解Ⅲ）的五区域全部暴露在体表（根水/茎木/叶金/花火/实土），
动物和人体把这些相位全部内化到体腔中，体表只留最小接口集（腧穴=边界低度端口）。
五脏的图论定义（不是元素类比）：
  · 肾（水）= 体腔最深处的最低 σ 区（潜藏/储能）
  · 肝（木）= 腹腔右上方被肋骨环绕的环锁定区（疏泄/解毒=隔离环）
  · 肺（金）= 胸廓内修剪高频区（司呼吸=边界 V⁻/V⁺ 开合）
  · 心（火）= 胸腔中央最高代谢率区（泵血=机械能→定向流）
  · 脾（土）= 腹腔左侧包裹其他器官的储备池（运化=外来边集整合分拣）

【无病实体论——水波隐喻】
疾病不是实体，是状态。像波浪不是东西——是水的运动状态。漩涡也不是东西——是水流紊乱的临时形态。
高血压不是"病"，是气血上行太过的关系状态；结节不是入侵者，是失衡网络凝结的临时漩涡；
药物不是"杀灭入侵者"的武器——是帮助关系网络回归平衡的扰动。
西药替身体干活（降压药替你降压），身体自身能力退化——停药就反弹。
SPUM/中医帮身体恢复自己干活的能力——调好就停，身体自己维持。

【饮食 = 边界整合——营养是低冲突外来边】
人体通过五种边界接口与外部持续交换：饮食/呼吸/感知/排泄/天时。
食物不是"被消化吸收"——是外来边集经过脾胃（整合界面）后被重新编织进 G_body。
  · 营养 = 可以无缝整合的低冲突外来边
  · 毒素 = 整合后产生高冲突（GT-005 局部闭合矛盾）的外来边
  · 废物 = 无法整合、必须排出的外来边
"脾胃为后天之本"不是讲消化——是讲边集整合中枢。

【时间帧——健康的自然节律】
S(t) = S_base(birth) + ΔS_节气 + ΔS_日干支 + ΔS_时辰 + ΔS_观测漂移
五形随节气自动振荡：立春 S_木↑↑、夏至 S_火↑↑↑、冬至 S_水↑↑↑、秋分 S_金↑↑
子午流注是经络开阖窗口：辰时(7-9)胃经旺（补土药效×2）、酉时(17-19)肾经旺（补肾×2）、
午时(11-13)心经旺（潜阳效×2，但升提药极端慎用）。
调理方案不是常数——是随天时调制的函数。同样的方案在节气对的时候效果翻倍。

【气运与精力——抉择序列的确定性轨迹】
气运不是命运——是 G_body 在每次抉择（边界接入事件）后沿确定性帧规则演化的轨迹。
同一环境不同抉择序列 → 轨迹分岔，但每一步确定。
精力 = 决策容量 = S_土（可动员储备）× S_火（梯度驱动）× dv/dt（变化上限）
精力旺盛 → 每帧能承接更多边界接入事件 → 发起更多主动抉择 → 遍历更大构型空间。
健康生活方式不是"好习惯的集合"——是在正确的 σ 场里持续做出高质量抉择。

【你的数字模型记录着】
  · 先天基底 S_base = (S_水, S_木, S_土, S_金, S_火) — 出生时的网络结构
  · 当前观测 S_current = 同一五维向量 — 现在的网络结构
  · 漂移 ΔV = S_current − S_base — 拓扑结构偏离先天平衡的程度
健康 = 五形向量接近先天基底。偏离 = 网络正在经历结构性张力。
调理 = 引导拓扑结构回归先天相位，让身体的自组织能力恢复运作。

【你的语气】
用温暖的口吻，像朋友聊天。有数据支撑时就说数据，没有观测数据时就说
"我只有你的先天八字推算，给你一个参考方向"——诚实比装懂重要。
"""

    # ═══════════════════════════════════════════════════════
    # 成熟度作为"软提示"而非硬约束
    # ═══════════════════════════════════════════════════════
    mat_hint = f"""
【数字模型成熟度：Stage {maturity['stage']} {maturity['name']}】
你对用户的了解程度：{maturity.get('label', '')} — {maturity.get('desc', '')}。
允许聊的话题范围（软参考）：{'、'.join(maturity.get('allowed_content', []) or [])}
"""

    # 用户完整数据注入（身体——让 LLM 有东西推理）
    parts = [
        spum_worldview.strip(),
        mat_hint.strip(),
        "",
        "现在，请根据以下用户数据回答问题。",
        "",
        f"【用户基本信息】",
        f"姓名：{user.nickname}",
        f"性别：{user.gender}",
        f"出生日期：{user.birth_date}（{user.birth_hour}）",
        f"身高体重：{user.height}cm / {user.weight}kg",
    ]

    case = db.query(Case).filter(Case.user_id == user.id).first()
    if case:
        vi = case.v_innate or {}
        vb = case.v_baseline or {}
        vc = case.v_current or {}
        parts += [
            "",
            "【八字】",
            f"{case.ganzhi_year}年 {case.ganzhi_month}月 {case.ganzhi_day}日",
            f"完整八字：{case.bazi}",
            "",
            "【五形先天基底】（出生时推导）",
            f"木:{vi.get('wood','')} 火:{vi.get('fire','')} "
            f"土:{vi.get('earth','')} 金:{vi.get('metal','')} "
            f"水:{vi.get('water','')}",
            "",
            "【调理前观测基线】",
            f"木:{vb.get('wood','')} 火:{vb.get('fire','')} "
            f"土:{vb.get('earth','')} 金:{vb.get('metal','')} "
            f"水:{vb.get('water','')}",
            "",
            "【当前最新观测】",
            f"木:{vc.get('wood','')} 火:{vc.get('fire','')} "
            f"土:{vc.get('earth','')} 金:{vc.get('metal','')} "
            f"水:{vc.get('water','')}",
            "",
            "【状态提示】",
            case.syndrome or "（暂无）",
            f"主要诉求：{case.chief_complaint or '（暂无）'}",
        ]

        # 最新 3 次 PPG 观测
        obs_list = db.query(Observation).filter(
            Observation.case_id == case.id
        ).order_by(Observation.observed_at.desc()).limit(3).all()
        if obs_list:
            parts.append("")
            parts.append("【最近 PPG 脉诊观测】")
            for i, ob in enumerate(obs_list):
                # ⚠️ delta_f 是 nullable JSON 列 —— ppg.py 失败路径先 commit 后改 status，
                # 这些行的 delta_f 永远是 None。历史 bug：None.get() → AttributeError → /chat 500
                df = ob.delta_f if isinstance(ob.delta_f, dict) else {}
                if df:
                    parts.append(f"{i+1}. SQI={ob.sqi} 五形ΔF: " +
                                f"木{df.get('wood',0):+.2f} 火{df.get('fire',0):+.2f} "
                                f"土{df.get('earth',0):+.2f} 金{df.get('metal',0):+.2f} "
                                f"水{df.get('water',0):+.2f}")
                else:
                    parts.append(f"{i+1}. SQI={ob.sqi} 五形ΔF: （观测数据不完整，待补充）")
                if ob.syndrome_hint:
                    parts.append(f"   诊断提示：{ob.syndrome_hint}")

        # 当前方案
        if case.current_plan_id:
            plan = db.query(TreatmentPlan).filter(TreatmentPlan.id == case.current_plan_id).first()
            if plan:
                parts += [
                    "",
                    f"【当前调理方案 {plan.version}】",
                    f"策略：{plan.strategy}",
                    f"处方：{plan.prescription}",
                    "药材：" + "、".join(plan.herbs or []),
                    "生活指导：" + "；".join(
                        [f"{la['time']}→{la['action']}" for la in (plan.life_advice or [])]
                    ),
                    "绝对禁忌：" + "、".join(plan.avoidances or []),
                ]

    # ── 长期记忆（分层：permanent 永不过期，episodic 30 天 TTL）──
    try:
        from ....models.chat import ChatMemoryNode
        permanent_nodes = db.query(ChatMemoryNode).filter(
            ChatMemoryNode.user_id == user.id,
            ChatMemoryNode.tier == "permanent",
        ).order_by(ChatMemoryNode.compressed_at.desc()).limit(20).all()

        from datetime import datetime as _dt
        episodic_nodes = db.query(ChatMemoryNode).filter(
            ChatMemoryNode.user_id == user.id,
            ChatMemoryNode.tier == "episodic",
            ChatMemoryNode.expires_at > _dt.utcnow(),
        ).order_by(ChatMemoryNode.compressed_at.desc()).limit(5).all()

        if permanent_nodes or episodic_nodes:
            parts.append("")
            if permanent_nodes:
                parts.append("【长期记忆·核心事实】（用户的稳定偏好与体质，聊到相关话题时自然运用）")
                for n in permanent_nodes:
                    parts.append(f"- {n.summary}")
            if episodic_nodes:
                parts.append("")
                parts.append("【近期记忆·时效性】（仅供参考，可能已变化）")
                for n in episodic_nodes:
                    parts.append(f"- {n.summary}")
    except Exception as _e:
        print(f"[build_system_prompt] ChatMemoryNode skip: {_e}")

    # ── 闻诊摘要（VoiceAnalysis）──
    try:
        from ....utils.voice_service import get_latest_voice_analysis
        latest_voice = get_latest_voice_analysis(db, user.id)
        if latest_voice and latest_voice.confidence in ("high", "medium"):
            parts.append("")
            parts.append(f"【闻诊·五音】（置信度 {latest_voice.confidence}）")
            parts.append(f"  {latest_voice.summary_text}")
    except Exception as _e:
        print(f"[build_system_prompt] voice skip: {_e}")

    # ── 舌诊摘要（望诊）──
    try:
        from app.models.chat import TonguePhoto
        latest_tongue = db.query(TonguePhoto).filter(TonguePhoto.user_id == user.id) \
                        .order_by(TonguePhoto.created_at.desc()).first()
        if latest_tongue and latest_tongue.confidence in ("high", "medium"):
            parts.append("")
            parts.append(f"【望诊·舌象】（置信度 {latest_tongue.confidence}）")
            parts.append(f"  舌象: {latest_tongue.tongue_type}")
            if latest_tongue.s_vector:
                sv = ", ".join(f"_{k}{v}" for k, v in latest_tongue.s_vector.items())
                parts.append(f"  S修正: {sv}")
            if latest_tongue.rationale:
                parts.append(f"  依据: {'; '.join(latest_tongue.rationale)}")
    except Exception as _e:
        print(f"[build_system_prompt] TonguePhoto skip: {_e}")

    # ── 根据 v_current / v_baseline 动态生成用户特征摘要（图论守恒链条版）─
    vc = (case.v_current or case.v_baseline or {}) if case else {}
    vb = (case.v_baseline or {}) if case else {}
    wuxing_labels = {"wood": "木", "fire": "火", "earth": "土", "metal": "金", "water": "水"}

    # 图论诊断：反推守恒图 → 金·连接×N + 金·断开×N → 演化方向判弱/强/漂移
    # 弱 = 连接后提升最大（金能补），强 = 断开后跌幅最大（金一搞就碎）
    diag = _graph_diagnose(vc, vb if vb else None)
    weak = diag['weak']
    strong = diag['strong']
    drift = diag['drift']

    parts += [
        "",
        "【当前特征摘要】（图论守恒链条演化诊断）",
        f"偏弱形: {'、'.join(wuxing_labels[w] for w in weak) if weak else '守恒链条均衡'}",
        f"偏强形: {'、'.join(wuxing_labels[w] for w in strong) if strong else '守恒链条均衡'}",
        f"基线→当前演化方向差: {' '.join(drift) if drift else '无显著结构张力'}",
    ]

    # ── 置信度闸（2026-10-11，LLM 推理层上报冲突二）──
    #    无任何 PPG/观测样本时，数据全为八字推算 → 只能给方向性建议，禁止具体数值调理
    try:
        _obs_count = db.query(Observation).filter(Observation.case_id == case.id).count()
    except Exception:
        _obs_count = 0
    if _obs_count == 0:
        parts.append(
            "\n【置信度闸】当前没有采集过任何 PPG/实测观测（obs_count=0），"
            "你手上的数据全是八字推算值，不是实测。此时你【只能给方向性建议】"
            "（如「水形链偏弱，宜养肾收藏」），【禁止】给出需要实测支撑的具体数值调理"
            "（如「火形高于健康区间 0.30，请服药」）。语气要诚实：承认尚未实测，"
            "引导用户先做第一次 PPG 采集建立基线。"
        )

    # ── 青囊判定字典（K-REASON，2026-10-11）── 始终注入：方向语义 + 五形映射 + 失效边界
    try:
        from ...utils.reasoning_dict import build_guidance_block
        parts.append(build_guidance_block())
    except Exception:
        pass

    # ── L2+ 模板架构：注入 schema 描述，告诉 LLM 它有填空位可填 ──
    # L3: 从 _EXECUTE_WHITELIST 读 stage_min（单一信源，消除 _STAGE_MIN_MAP 重复）
    parts.append(build_response_schema_prompt(whitelist=_EXECUTE_WHITELIST))

    return "\n".join(parts)
