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


def run_seed(db: Session):
    print("🌱 开始种子数据注入...")
    u = seed_hu_yuntao(db)
    s = seed_shop_items(db)
    print(f"  [seed] 完成：胡运涛={'✅' if u else '⏭️ 已存在'}，商城={s} 条新建")
