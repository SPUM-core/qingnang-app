"""胡运涛种子数据 - 将前端 hu_case.js 的完整数据注入 SQLite"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json

from app.models import User, Case, Observation, TreatmentPlan, DoctorProfile
from app.utils.security import hash_pwd

HU_YUNTAO = {
    # 用户基本
    "qingnang_id": "QN-SPUM-CASE-002",
    "phone": "138******00",
    "password": "qingnang2026",
    "nickname": "胡运涛",
    "gender": "male",
    "birth_date": "1987-09-12",
    "birth_hour": "寅时",
    "height": 173,
    "weight": 57.7,
    "is_doctor": False,
    "is_onboarded": True,

    # 八字（寅时确定版）
    "bazi": "丁卯 己酉 甲子 丙寅",
    "ganzhi_year": "丁卯",
    "ganzhi_month": "己酉",
    "ganzhi_day": "甲子",

    # ═══ S_0^0 先天基底（v5.4 出生事件校核版）═══
    # 量化：木↑↑↑→60  火↑↑(郁)→58  土↓→35  金↔→50  水↔(伤)→48
    "v_innate": {"wood": 60, "fire": 58, "earth": 35, "metal": 50, "water": 48},
    # v_baseline = 初诊 S_effective（与 v_innate 同值，治疗前即 S_0 状态）
    "v_baseline": {"wood": 60, "fire": 58, "earth": 35, "metal": 50, "water": 48},
    # v_current = 最新观测（2026-09-15 湿遏·火衰·水滞）
    "v_current": {"wood": 51.2, "fire": 32.4, "earth": 39.2, "metal": 50.8, "water": 26.0},

    "syndrome": "湿遏·气结74%·土枯·水形精·火形悖论",
    "chief_complaint": "长期疲乏·失眠·食欲不振·性欲旺盛（相火妄动）·百会穴麻木疼痛",

    # ═══ 12 次真实 PPG 观测（来自青囊/病历/胡运涛/数据/脉象/）═══
    # 转换公式：v_obs = 50 + ΔF * 40
    # 按时间升序排列（后端查询时 asc 顺序）
    "observations": [
        # day=1  07-18 18:00 — 首诊（假性充盈：土+0.60→74 临床为 S_土↓↓↓）
        {"date": "2026-07-18", "sqi": 76,
         "delta_f": {"wood": -0.36, "fire": +0.62, "earth": +0.60, "metal": -0.28, "water": -0.60},
         "v_obs": {"wood": 35.6, "fire": 74.8, "earth": 74.0, "metal": 38.8, "water": 26.0},
         "syndrome_hint": "脾虚湿困+上热下寒·PPG土+0.60=假性充盈≠真旺"},
        # day=2  07-18 18:01 — 重复采集
        {"date": "2026-07-18", "sqi": 77,
         "delta_f": {"wood": -0.35, "fire": +0.67, "earth": +0.60, "metal": -0.28, "water": -0.60},
         "v_obs": {"wood": 36.0, "fire": 76.8, "earth": 74.0, "metal": 38.8, "water": 26.0},
         "syndrome_hint": "脾虚湿困+上热下寒"},
        # day=3  07-21 18:17 — 湿热化火（心率84.8·舌厚黄苔·肝俞痛）
        {"date": "2026-07-21", "sqi": 74,
         "delta_f": {"wood": -0.31, "fire": +0.75, "earth": +0.60, "metal": -0.25, "water": -0.60},
         "v_obs": {"wood": 37.6, "fire": 80.0, "earth": 74.0, "metal": 40.0, "water": 26.0},
         "syndrome_hint": "湿热化火·舌厚黄苔·肝俞痛"},
        # day=4  08-02 15:57 — 气滞血瘀（置信度88%·服药前）
        {"date": "2026-08-02", "sqi": 84,
         "delta_f": {"wood": +0.50, "fire": -0.25, "earth": -0.35, "metal": +0.40, "water": -0.60},
         "v_obs": {"wood": 70.0, "fire": 40.0, "earth": 36.0, "metal": 66.0, "water": 26.0},
         "syndrome_hint": "气滞血瘀（置信度88%）"},
        # day=5  08-02 16:06 — 火衰（温差趋零）
        {"date": "2026-08-02", "sqi": 63,
         "delta_f": {"wood": +0.32, "fire": -0.51, "earth": -0.44, "metal": +0.26, "water": -0.60},
         "v_obs": {"wood": 62.8, "fire": 29.6, "earth": 32.4, "metal": 60.4, "water": 26.0},
         "syndrome_hint": "火衰（温差趋零）"},
        # day=6  08-02 16:17 — 收敛正常（服方后）
        {"date": "2026-08-02", "sqi": 84,
         "delta_f": {"wood": +0.11, "fire": -0.07, "earth": -0.13, "metal": +0.09, "water": +0.11},
         "v_obs": {"wood": 54.4, "fire": 47.2, "earth": 44.8, "metal": 53.6, "water": 54.4},
         "syndrome_hint": "五形趋于正常（肝气郁结44%）"},
        # day=7  08-02 16:23 — 收敛正常
        {"date": "2026-08-02", "sqi": 85,
         "delta_f": {"wood": +0.15, "fire": -0.02, "earth": -0.12, "metal": +0.12, "water": +0.19},
         "v_obs": {"wood": 56.0, "fire": 49.2, "earth": 45.2, "metal": 54.8, "water": 57.6},
         "syndrome_hint": "五形趋于正常（肝气郁结53%）"},
        # day=8  09-08 12:50 — 服方on（v5.7桂枝汤·透火郁主频效验）
        {"date": "2026-09-08", "sqi": 80,
         "delta_f": {"wood": +0.07, "fire": +0.15, "earth": -0.07, "metal": +0.06, "water": +0.10},
         "v_obs": {"wood": 52.8, "fire": 56.0, "earth": 47.2, "metal": 52.4, "water": 54.0},
         "syndrome_hint": "正常脉象（服方on·透火郁主频效验）"},
        # day=9  09-08 12:51 — 服方on
        {"date": "2026-09-08", "sqi": 85,
         "delta_f": {"wood": +0.04, "fire": +0.18, "earth": -0.01, "metal": +0.03, "water": +0.18},
         "v_obs": {"wood": 51.6, "fire": 57.2, "earth": 49.6, "metal": 51.2, "water": 57.2},
         "syndrome_hint": "正常脉象（服方on）"},
        # day=10 09-10 16:08 — 停药off（on-off验证·肝郁87%·水亏）
        {"date": "2026-09-10", "sqi": 71,
         "delta_f": {"wood": +0.13, "fire": -0.13, "earth": -0.22, "metal": +0.10, "water": -0.29},
         "v_obs": {"wood": 55.2, "fire": 44.8, "earth": 41.2, "metal": 54.0, "water": 38.4},
         "syndrome_hint": "停药off·肝郁87%·水亏-0.29"},
        # day=11 09-12 18:35 — 爬山后气阴两虚
        {"date": "2026-09-12", "sqi": 71,
         "delta_f": {"wood": -0.19, "fire": -0.22, "earth": -0.24, "metal": -0.15, "water": -0.21},
         "v_obs": {"wood": 42.4, "fire": 41.2, "earth": 40.4, "metal": 44.0, "water": 41.6},
         "syndrome_hint": "气阴两虚·清阳不升"},
        # day=12 09-15 11:25 — 湿遏·火衰-0.41·水滞-0.62
        {"date": "2026-09-15", "sqi": 59,
         "delta_f": {"wood": +0.03, "fire": -0.44, "earth": -0.27, "metal": +0.02, "water": -0.60},
         "v_obs": {"wood": 51.2, "fire": 32.4, "earth": 39.2, "metal": 50.8, "water": 26.0},
         "syndrome_hint": "湿遏·火衰-0.41·水滞-0.62"},
    ],

    # 方案版本链（9 版）
    "plans": [
        {"version": "v7.0", "date": "2026-09-15", "type": "iteration",
         "strategy": "温土疏木、化气利水",
         "prescription": "苓桂术甘汤 + 白芍 10g + 砂仁 3g",
         "herbs": ["茯苓 15g", "桂枝 10g", "白术 15g", "炙甘草 6g", "白芍 10g", "砂仁 3g"],
         "life_advice": [
             {"time": "晨起", "action": "温淡盐水 200ml"},
             {"time": "戌时 19-21", "action": "泡脚 40℃ / 15min"},
             {"time": "三餐", "action": "小米粥 + 蒸蛋 + 鲫鱼汤"},
             {"time": "申时 15-17", "action": "散步 30min"},
         ],
         "avoidances": ["苦寒直折", "安眠药", "岫玉翡翠", "冷饮", "晚餐后进食"],
         "reasoning": "v6.0 后土形从 40→48（+20%），湿遏缓解。但气结仍 74%，加白芍疏木、砂仁醒脾。"},
        {"version": "v6.0.1", "date": "2026-09-12", "type": "iteration",
         "strategy": "温土益气",
         "prescription": "桂芪对 + 茯苓 12g",
         "herbs": ["桂枝 10g", "黄芪 15g", "茯苓 12g"],
         "life_advice": [{"time": "戌时", "action": "泡脚 15min"}],
         "avoidances": ["苦寒直折"],
         "reasoning": "v6.0 后略有燥热反馈，去枸杞子。"},
        {"version": "v6.0", "date": "2026-09-10", "type": "validation",
         "strategy": "温土疏木 + 补火",
         "prescription": "桂枝汤 + 枸杞子 15g",
         "herbs": ["桂枝 12g", "白芍 12g", "炙甘草 6g", "大枣 6枚", "生姜 10g", "枸杞子 15g"],
         "life_advice": [{"time": "午时", "action": "闭目养神 20min"}, {"time": "睡前", "action": "蜜蜡佩戴"}],
         "avoidances": ["岫玉翡翠（寒）"],
         "reasoning": "on-off 验证方案，加枸杞子补火形。"},
        {"version": "v5.7", "date": "2026-09-08", "type": "initial",
         "strategy": "最小试探方",
         "prescription": "茯苓 15g + 桂枝 6g",
         "herbs": ["茯苓 15g", "桂枝 6g"],
         "life_advice": [{"time": "晨起", "action": "温淡盐水"}],
         "avoidances": ["苦寒直折", "安眠药"],
         "reasoning": "最小有效剂量试探，验证温土方向。"},
        {"version": "v5.4", "date": "2026-07-18", "type": "initial",
         "strategy": "出生事件校核后重建方案",
         "prescription": "四君子汤 + 少量桂枝",
         "herbs": ["党参 10g", "白术 12g", "茯苓 15g", "炙甘草 6g", "桂枝 5g"],
         "life_advice": [{"time": "戌时", "action": "泡脚"}],
         "avoidances": ["苦寒直折"],
         "reasoning": "重要发现：出生时木形基线比预期高 15%，重新校准先天基底。"},
        {"version": "v5.2", "date": "2026-07-01", "type": "initial",
         "strategy": "健脾益气",
         "prescription": "四君子汤",
         "herbs": ["党参 10g", "白术 12g", "茯苓 15g", "炙甘草 6g"],
         "life_advice": [{"time": "三餐", "action": "小米粥为主"}],
         "avoidances": ["生冷"],
         "reasoning": "第一次正式方案。"},
    ]
}


def seed_hu_yuntao(db: Session) -> bool:
    """返回 True=首次注入  False=已存在跳过"""
    from app.models import User, Case

    existing = db.query(User).filter(User.qingnang_id == HU_YUNTAO["qingnang_id"]).first()
    if existing:
        print(f"  [seed] 胡运涛已存在 (id={existing.id})，跳过")
        return False

    # 1. 创建 User
    user = User(
        qingnang_id=HU_YUNTAO["qingnang_id"],
        phone=HU_YUNTAO["phone"],
        password_hash=hash_pwd(HU_YUNTAO["password"]),
        nickname=HU_YUNTAO["nickname"],
        gender=HU_YUNTAO["gender"],
        birth_date=HU_YUNTAO["birth_date"],
        birth_hour=HU_YUNTAO["birth_hour"],
        height=HU_YUNTAO["height"],
        weight=HU_YUNTAO["weight"],
        is_doctor=HU_YUNTAO["is_doctor"],
        is_onboarded=HU_YUNTAO["is_onboarded"],
        v_base=HU_YUNTAO["v_baseline"],
    )
    db.add(user)
    db.flush()
    print(f"  [seed] User created: id={user.id}")

    # 2. 创建 Case
    case = Case(
        user_id=user.id,
        bazi=HU_YUNTAO["bazi"],
        ganzhi_year=HU_YUNTAO["ganzhi_year"],
        ganzhi_month=HU_YUNTAO["ganzhi_month"],
        ganzhi_day=HU_YUNTAO["ganzhi_day"],
        v_innate=HU_YUNTAO["v_innate"],
        v_baseline=HU_YUNTAO["v_baseline"],
        v_current=HU_YUNTAO["v_current"],
        syndrome=HU_YUNTAO["syndrome"],
        chief_complaint=HU_YUNTAO["chief_complaint"],
    )
    db.add(case)
    db.flush()
    print(f"  [seed] Case created: id={case.id}")

    # 3. 创建 Observations（按日期降序）
    obs_ids = []
    for i, ob in enumerate(reversed(HU_YUNTAO["observations"])):
        obs = Observation(
            case_id=case.id,
            source="cheezPPG",
            sqi=ob["sqi"],
            delta_f=ob["delta_f"],
            v_obs=ob["v_obs"],
            syndrome_hint=ob["syndrome_hint"],
            observed_at=datetime.strptime(ob["date"], "%Y-%m-%d") + timedelta(hours=i),
        )
        db.add(obs)
        db.flush()
        obs_ids.append(obs.id)
    print(f"  [seed] Observations created: {len(obs_ids)}")

    # 4. 创建 TreatmentPlans（按日期降序）
    plan_ids = []
    for i, pl in enumerate(reversed(HU_YUNTAO["plans"])):
        tp = TreatmentPlan(
            case_id=case.id,
            version=pl["version"],
            plan_type=pl["type"],
            strategy=pl["strategy"],
            prescription=pl["prescription"],
            herbs=pl["herbs"],
            life_advice=pl["life_advice"],
            avoidances=pl["avoidances"],
            reasoning=pl["reasoning"],
            doctor_signed=True,
            pushed_at=datetime.strptime(pl["date"], "%Y-%m-%d") + timedelta(hours=9),
            user_confirmed=True,
            from_obs_id=obs_ids[min(i, len(obs_ids)-1)] if obs_ids else None,
            created_at=datetime.strptime(pl["date"], "%Y-%m-%d"),
        )
        db.add(tp)
        db.flush()
        plan_ids.append(tp.id)

    # 设置 current_plan_id = 最新版
    case.current_plan_id = plan_ids[-1] if plan_ids else None
    print(f"  [seed] TreatmentPlans created: {len(plan_ids)}, current=v7.0(id={case.current_plan_id})")

    db.commit()
    print("  [seed] ✅ 胡运涛完整案例注入完成")
    return True


def seed_shop_items(db: Session) -> int:
    """商城种子数据（12 款）"""
    from app.models import ShopItem
    CATALOG = [
        {"sku": "shop-001", "title": "茯苓茶 · 健脾祛湿", "category": "herb", "price": 38.0,
         "spum_tags": {"suitable": ["earth", "wood"], "avoid": ["fire"], "wuxing_elem": "earth"},
         "provider_url": "#"},
        {"sku": "shop-002", "title": "小米粥料包 · 温养土形", "category": "herb", "price": 22.0,
         "spum_tags": {"suitable": ["earth"], "wuxing_elem": "earth"}, "provider_url": "#"},
        {"sku": "shop-003", "title": "蜜蜡手串 · 温润不燥", "category": "home", "price": 268.0,
         "spum_tags": {"suitable": ["earth"], "avoid": ["fire"], "wuxing_elem": "earth"}, "provider_url": "#"},
        {"sku": "shop-004", "title": "红玛瑙戒指 · 补火形", "category": "home", "price": 188.0,
         "spum_tags": {"suitable": ["water"], "wuxing_elem": "fire"}, "provider_url": "#"},
        {"sku": "shop-005", "title": "绿色棉麻衬衫 · 木形宜色", "category": "clothing", "price": 298.0,
         "spum_tags": {"suitable": ["wood"], "wuxing_elem": "wood"}, "provider_url": "#"},
        {"sku": "shop-006", "title": "阔叶绿植套装 · 客厅补木", "category": "home", "price": 158.0,
         "spum_tags": {"suitable": ["wood"], "wuxing_elem": "wood"}, "provider_url": "#"},
        {"sku": "shop-007", "title": "艾叶泡脚包 · 温经散寒", "category": "daily", "price": 48.0,
         "spum_tags": {"suitable": ["earth", "wood"], "avoid": ["fire"], "wuxing_elem": "earth"},
         "review_count": 4, "avg_rating": 4.5},
        {"sku": "shop-008", "title": "加湿器 · 滋水护印", "category": "home", "price": 398.0,
         "spum_tags": {"suitable": ["water"], "wuxing_elem": "water"}, "provider_url": "#"},
        {"sku": "shop-009", "title": "鲫鱼汤料包 · 利水不寒", "category": "herb", "price": 32.0,
         "spum_tags": {"suitable": ["earth", "water"], "wuxing_elem": "water"}, "provider_url": "#"},
        {"sku": "shop-010", "title": "暖黄 2700K 台灯 · 相火归位", "category": "home", "price": 168.0,
         "spum_tags": {"suitable": ["fire"], "wuxing_elem": "fire"}, "provider_url": "#"},
        {"sku": "shop-011", "title": "山药薏米芡实粉", "category": "herb", "price": 68.0,
         "spum_tags": {"suitable": ["earth"], "wuxing_elem": "earth"}, "provider_url": "#"},
        {"sku": "shop-012", "title": "棉麻家居服 · 透气舒适", "category": "clothing", "price": 258.0,
         "spum_tags": {"suitable": ["wood", "earth"], "wuxing_elem": "wood"}, "provider_url": "#"},
    ]
    created = 0
    for item in CATALOG:
        exist = db.query(ShopItem).filter(ShopItem.sku == item["sku"]).first()
        if exist: continue
        db.add(ShopItem(**item))
        created += 1
    if created:
        db.commit()
        print(f"  [seed] ShopItems created: {created}")
    return created


# ══════════════════════════════════════════════════════════════════════════════
# 高素娟（CASE-001 · 雍虚共轭 · 一贯煎合增液汤加味）
# center=20 概率分布口径（v_innate/v_baseline/v_obs 统一）
# ══════════════════════════════════════════════════════════════════════════════

GAO_SUJUAN = {
    # 用户基本（center=20 概率分布口径）
    "qingnang_id": "SPUM-TCM-CASE-001",
    "phone": "139******01",
    "password": "qinxuan2026",
    "nickname": "高素娟",
    "gender": "female",
    "birth_date": "1989-08-02",      # 己巳年七月初二（阳历）
    "birth_hour": "戌时",            # 时柱临界 19:29，两盘壅虚共轭均成立
    "height": 162,
    "weight": 52,
    "city": "开封",                   # 114.3°E → 真太阳时 ≈ −29 min
    "is_doctor": False,
    "is_onboarded": True,

    # 八字（三柱确定性 · 时柱临界）
    "bazi": "己巳 辛未 乙未",          # 时柱待确认：丙戌 vs 乙酉
    "ganzhi_year": "己巳",
    "ganzhi_month": "辛未",
    "ganzhi_day": "乙未",

    # ═══ v_innate · 藏干概率分布（center=20，总和≈100）═══
    # bazi.py make_bazi 三柱版精确计算：
    #   己巳: 己(土1.0)+巳藏丙0.7庚0.2戊0.1 → 土1.1 火0.7 金0.2
    #   辛未: 辛(金1.0)+未藏己0.7丁0.2乙0.1 → 金1.0 土0.8 火0.2 木0.1
    #   乙未: 乙(木1.0)+未藏己0.7丁0.2乙0.1 → 木1.1 土0.7 火0.2
    # 合计: 木1.2 火1.1 土2.6 金1.2 水0 → 归一化≈木20 火18 土43 金20 水0
    #   🟢 印证病历：格局无水 · 乙木弱 · 土壅埋木
    "v_innate": {"wood": 20, "fire": 18, "earth": 43, "metal": 20, "water": 0},
    "v_baseline": {"wood": 20, "fire": 18, "earth": 43, "metal": 20, "water": 0},
    # v_current = 最新观测 (2026-10-02 · 新方升提过度)
    # v_obs = baseline + delta_f * 20（center=20 口径统一）
    "v_current":  {"wood": 21.6, "fire": 17.2, "earth": 45.2, "metal": 22.8, "water": 0},

    "syndrome": "壅虚共轭 · 乙木弱不能疏土 · 血海深层空虚",
    "chief_complaint": "长期月经稀发（3-4月一行）+ 白带过多 + 精神不振",

    # ═══ 2 次真实 PPG 观测（病历 数据/脉象/ 2026-09-05 · 2026-10-02）═══
    # delta_f: PPG 引擎原始输出（center=0）
    # v_obs = v_baseline + delta_f * 20（center=20 口径统一，clamp ≥0）
    "observations": [
        # day=1  2026-09-05 · rec_20260905_124303 · SQI 0.747 · 重采为准
        {"date": "2026-09-05", "sqi": 75,
         "delta_f": {"wood": +0.15, "fire": -0.21, "earth": -0.12, "metal": +0.12, "water": -0.50},
         "v_obs": {"wood": 23.0, "fire": 13.8, "earth": 40.6, "metal": 22.4, "water": 0},
         "syndrome_hint": "肝气郁结93% + 火衰48% + 气血两虚35%（水↓跨采最稳健·肾虚核心）"},
        # day=2  2026-10-02 · SQI 0.808 · 换方后瘙痒·新方升提过度
        {"date": "2026-10-02", "sqi": 81,
         "delta_f": {"wood": +0.08, "fire": -0.04, "earth": +0.11, "metal": +0.14, "water": -0.03},
         "v_obs": {"wood": 21.6, "fire": 17.2, "earth": 45.2, "metal": 22.8, "water": 0},
         "syndrome_hint": "心阳虚80% + 气阴两虚46% · 土从虚→壅·滑品质0.20新湿浊·升提过度印证"},
    ],

    # 方案版本链（简化：herbs 留空，避免 Stage<4 用户看到具体药材名）
    "plans": [
        {"version": "v2.0", "date": "2026-10-02", "type": "iteration",
         "strategy": "恢复一贯煎方向·佐使微调·干姜3补火化",
         "prescription": "一贯煎合增液汤加味·秋令方v2（君主频不动·佐使层强化护传导）",
         "herbs": [],
         "life_advice": [
             {"time": "每日", "action": "每日1剂·水煎服·早晚分服"},
             {"time": "经期", "action": "去五味子·浮小麦·当归改15加川芎6活血调经"},
             {"time": "经后", "action": "加熟地15·阿胶9填血海"},
         ],
         "avoidances": ["升提单线铁律", "浮越不泻", "辛散走表（生姜慎·干姜宜）", "多线叠加"],
         "reasoning": "原方一贯煎服5天因滋腻碍脾未微调即停→换方升提过度（黄芪30+柴胡9+生姜3+党参15同相过冲）→浑身瘙痒。v2撤新方升提驱动·君主频不动·佐使层加茯苓10减生地麦冬3g·干姜3守中助气化。"},
        {"version": "v1.0", "date": "2026-09-05", "type": "initial",
         "strategy": "滋阴润燥·降气敛肺·秋令方",
         "prescription": "一贯煎合增液汤加味·秋令方（每日1剂·单一统方）",
         "herbs": [],
         "life_advice": [
             {"time": "每日", "action": "每日1剂·水煎服·早晚分服"},
             {"time": "秋分前后", "action": "复诊调佐使·按燥气转凉微调"},
         ],
         "avoidances": ["辛散走表（生姜）", "升提单线", "多线叠加", "苦寒直折"],
         "reasoning": "雍虚共轭·停全部多线·改单一统方·君主频生地玄参ΔS_水↑慢脉冲·佐使川楝杏仁开路·术陈护传导·五味浮麦敛护。9/8服3日良响应（汗减·痰减）·9/10服5日过渡态（夜尿1→4·咽干·便粘=水至而火未化·守方待水尖峰锁稳）。"},
    ],

    # ═══ 5 份复诊（TreatmentPlan plan_type=followup，复用方案版本链做时间线）═══
    # 2026-06-22 → 2026-09-08 → 2026-09-10 → 2026-10-02 时间线完整
    "followups": [
        {"version": "FU-07", "date": "2026-09-10", "type": "followup",
         "title": "服药5日反馈 · 水尖峰建立途中（过渡态）",
         "feedback": "夜尿 1→4 次（新）· 夜咽干仍存 · 晨便不顺畅·量少·粘",
         "symptoms": "夜尿频多 · 咽干 · 便粘不畅",
         "delta_summary": "S_水↑已投送 · S_火↓↓气化未同步驱动 → 阴液骤入而肾阳气化无力蒸腾",
         "decision": "守方不动（秋分 9/22 复诊前不加不减）",
         "reasoning": "阴虚主频（水尖峰）已起效投送（津总量上升）；同时暴露核心缺口：S_火↓↓ 肾阳气化不足（火衰48%·9/5脉诊兼证印证）——火不化水，津既不上承（咽干）、也不下润（便粘），反停蓄膀胱（夜尿频）。方向对，仅缺'气化'一环把水津拉回正常分配链路。",
         "next_step": "秋分（9/22）前后复诊调佐使；夜尿持续>3晚且口渴不缓解→微助肾气化/固泉（佐使层调度，君主频不动）",
         "outcome": "中性过渡信号（非负面）· 水至而气未化过渡态"},
        {"version": "FU-06", "date": "2026-09-08", "type": "followup",
         "title": "服药3日反馈 · 良响应首帧",
         "feedback": "出汗明显改善 · 痰有所减少 · 夜咽干仍存",
         "symptoms": "夜咽干（预期相位滞后）",
         "delta_summary": "Q_浮麦/五味敛护峰到位 ✅ · Q_术陈护传导生效 ✅",
         "decision": "守方不加减，待水尖峰主频建立",
         "reasoning": "汗减✅ = 佐4·五味浮麦「汗减·浮越收」验中；痰减✅ = 佐2·术陈「痰减」验中；咽干仍存系君·生地玄参厚味慢脉冲·水尖峰主频未建，属于预期相位滞后，非越界。",
         "next_step": "秋分（9/22）复诊调佐使。期间按观察调整判据自查。",
         "outcome": "✅ 良响应首帧"},
        {"version": "FU-05", "date": "2026-08-09", "type": "followup",
         "title": "经净 · 量质预警",
         "feedback": "经量极少·色淡 · 痰核仍增大",
         "symptoms": "经量极少 · 痰核增大",
         "delta_summary": "周期达标 ≠ 量质达标 · 血海深层空虚",
         "decision": "补土补肾已完成周期功能，但补而不化 → 需显式化痰 + 滋阴养血补海",
         "reasoning": "8/4 月经 38 天来潮，周期重启成功（S_土↑+S_水↑方向验证）。但经量极少·痰核增大 = 血海深层空虚仍在，补而不化，需下一步显式化痰并加大滋阴养血填血海力度。",
         "next_step": "下一周期复诊时调整方案方向",
         "outcome": "⚠️ 量质预警 · 待滋阴补海"},
        {"version": "FU-04", "date": "2026-08-04", "type": "followup",
         "title": "月经来潮 · 周期重启",
         "feedback": "月经 38 天周期 · 距上次显著缩短",
         "symptoms": "无新症状",
         "delta_summary": "S_土↑+S_水↑方向验证 · 周期功能已恢复",
         "decision": "补土补肾方向有效，继续观察量质",
         "reasoning": "月经 38 天来潮，较之前 3-4 月一行显著缩短。补土补肾（主要靠中成药，汤剂尚未正式服用）已完成周期重启。这是雍虚共轭治疗的第一个里程碑——周期恢复是后续量质提升的前提。",
         "next_step": "经净后（约 8/9）复诊评估量质",
         "outcome": "✅ 周期重启成功"},
        {"version": "FU-03", "date": "2026-06-22", "type": "followup",
         "title": "首诊建立基线",
         "feedback": "误服大黄蛰虫丸 2日剧烈反应（已停）· 后遗 S_金↑↑ 舌下青筋",
         "symptoms": "月经稀发（3-4月一行）· 白带过多 · 精神不振",
         "delta_summary": "壅虚共轭确认：S_土↓↓血海空虚 + S_木郁闭",
         "decision": "停所有多线杂治 · 改单一统方 · 滋阴润燥 · 降气敛肺",
         "reasoning": "雍虚共轭核心确认：乙木弱不能疏土 → 下垂性壅滞；血海深层空虚。误服大黄蛰虫丸（虫药走络过猛，雍虚共轭虚不受攻）后遗 S_金↑↑ 舌下青筋。立原则：停全部多线杂治，单一统方，君主频生地玄参ΔS_水↑慢脉冲。",
         "next_step": "2个月后月经周期复诊评估",
         "outcome": "📌 基线确立 · 雍虚共轭锁定"},
    ]
}


def seed_gao_sujuan(db: Session) -> bool:
    """返回 True=首次注入  False=已存在跳过"""
    from app.models import User, Case

    existing = db.query(User).filter(User.qingnang_id == GAO_SUJUAN["qingnang_id"]).first()
    if existing:
        print(f"  [seed] 高素娟已存在 (id={existing.id})，跳过")
        return False

    # 1. 创建 User
    user = User(
        qingnang_id=GAO_SUJUAN["qingnang_id"],
        phone=GAO_SUJUAN["phone"],
        password_hash=hash_pwd(GAO_SUJUAN["password"]),
        nickname=GAO_SUJUAN["nickname"],
        gender=GAO_SUJUAN["gender"],
        birth_date=GAO_SUJUAN["birth_date"],
        birth_hour=GAO_SUJUAN["birth_hour"],
        height=GAO_SUJUAN["height"],
        weight=GAO_SUJUAN["weight"],
        is_doctor=GAO_SUJUAN["is_doctor"],
        is_onboarded=GAO_SUJUAN["is_onboarded"],
        v_base=GAO_SUJUAN["v_baseline"],
    )
    db.add(user)
    db.flush()
    print(f"  [seed] User created: id={user.id}")

    # 2. 创建 Case
    case = Case(
        user_id=user.id,
        bazi=GAO_SUJUAN["bazi"],
        ganzhi_year=GAO_SUJUAN["ganzhi_year"],
        ganzhi_month=GAO_SUJUAN["ganzhi_month"],
        ganzhi_day=GAO_SUJUAN["ganzhi_day"],
        v_innate=GAO_SUJUAN["v_innate"],
        v_baseline=GAO_SUJUAN["v_baseline"],
        v_current=GAO_SUJUAN["v_current"],
        syndrome=GAO_SUJUAN["syndrome"],
        chief_complaint=GAO_SUJUAN["chief_complaint"],
    )
    db.add(case)
    db.flush()
    print(f"  [seed] Case created: id={case.id}")

    # 3. 创建 Observations（按日期降序）
    obs_ids = []
    for i, ob in enumerate(reversed(GAO_SUJUAN["observations"])):
        obs = Observation(
            case_id=case.id,
            source="cheezPPG",
            sqi=ob["sqi"],
            delta_f=ob["delta_f"],
            v_obs=ob["v_obs"],
            syndrome_hint=ob["syndrome_hint"],
            observed_at=datetime.strptime(ob["date"], "%Y-%m-%d") + timedelta(hours=10 + i),
        )
        db.add(obs)
        db.flush()
        obs_ids.append(obs.id)
    print(f"  [seed] Observations created: {len(obs_ids)}")

    # 4. 创建 TreatmentPlans（按日期降序）
    plan_ids = []
    for i, pl in enumerate(reversed(GAO_SUJUAN["plans"])):
        tp = TreatmentPlan(
            case_id=case.id,
            version=pl["version"],
            plan_type=pl["type"],
            strategy=pl["strategy"],
            prescription=pl["prescription"],
            herbs=pl["herbs"],
            life_advice=pl["life_advice"],
            avoidances=pl["avoidances"],
            reasoning=pl["reasoning"],
            doctor_signed=True,
            pushed_at=datetime.strptime(pl["date"], "%Y-%m-%d") + timedelta(hours=9),
            user_confirmed=True,
            from_obs_id=obs_ids[min(i, len(obs_ids)-1)] if obs_ids else None,
            created_at=datetime.strptime(pl["date"], "%Y-%m-%d"),
        )
        db.add(tp)
        db.flush()
        plan_ids.append(tp.id)

    case.current_plan_id = plan_ids[-1] if plan_ids else None
    print(f"  [seed] TreatmentPlans created: {len(plan_ids)}, current=v2.0(id={case.current_plan_id})")

    # 5. 创建 FollowUp 复诊记录（plan_type=followup，复用 TreatmentPlan 时间线）
    fu_count = 0
    for fu in reversed(GAO_SUJUAN.get("followups", [])):
        tp = TreatmentPlan(
            case_id=case.id,
            version=fu["version"],
            plan_type=fu["type"],   # "followup"
            strategy=fu["title"],   # 复诊标题
            prescription=fu["decision"],  # 处置/决策
            reasoning=fu["reasoning"],
            effectiveness={          # JSON 存完整复诊结构数据
                "feedback": fu["feedback"],
                "symptoms": fu.get("symptoms", ""),
                "delta_summary": fu.get("delta_summary", ""),
                "next_step": fu.get("next_step", ""),
                "outcome": fu.get("outcome", ""),
            },
            doctor_signed=True,
            pushed_at=datetime.strptime(fu["date"], "%Y-%m-%d") + timedelta(hours=14),
            user_confirmed=True,
            created_at=datetime.strptime(fu["date"], "%Y-%m-%d"),
        )
        db.add(tp)
        db.flush()
        fu_count += 1
    print(f"  [seed] FollowUp created: {fu_count}")

    db.commit()
    print("  [seed] ✅ 高素娟完整案例注入完成")
    return True


def run_seed(db: Session):
    print("🌱 开始种子数据注入...")
    g = seed_gao_sujuan(db)
    u = seed_hu_yuntao(db)
    s = seed_shop_items(db)
    print(f"  [seed] 完成：高素娟={'✅' if g else '⏭️ 已存在'}，胡运涛={'✅' if u else '⏭️ 已存在'}，商城={s} 条新建")
