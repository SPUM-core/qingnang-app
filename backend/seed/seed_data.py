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
    "birth_date": "1986-08-02",
    "birth_hour": "寅时",
    "height": 176,
    "weight": 78,
    "is_doctor": False,
    "is_onboarded": True,

    # 八字
    "bazi": "丁卯 己酉 甲子 丙寅",
    "ganzhi_year": "丙午",
    "ganzhi_month": "丁酉",
    "ganzhi_day": "癸酉",

    # 五形向量
    "v_innate": {"wood": 72, "fire": 55, "earth": 58, "metal": 68, "water": 65},
    "v_baseline": {"wood": 80, "fire": 70, "earth": 40, "metal": 50, "water": 60},
    "v_current": {"wood": 82, "fire": 68, "earth": 42, "metal": 51, "water": 58},

    "syndrome": "湿遏·气结74%·土枯·水形精·火形悖论",
    "chief_complaint": "长期疲乏，工作压力大，睡眠质量下降，午子冲节律异常",

    # 观测记录（8 次 PPG）
    "observations": [
        {"date": "2026-09-15", "sqi": 87,
         "delta_f": {"wood": -0.06, "fire": -0.41, "earth": -0.15, "metal": -0.04, "water": -0.62},
         "v_obs": {"wood": 47.6, "fire": 33.6, "earth": 44.0, "metal": 48.4, "water": 25.2},
         "syndrome_hint": "气结状态 74% 特征匹配，湿遏指标上升"},
        {"date": "2026-09-12", "sqi": 82,
         "delta_f": {"wood": -0.08, "fire": -0.38, "earth": -0.12, "metal": -0.05, "water": -0.58},
         "v_obs": {"wood": 45.2, "fire": 35.8, "earth": 45.5, "metal": 47.8, "water": 27.8},
         "syndrome_hint": "湿遏初现苗头，气结 68%"},
        {"date": "2026-09-10", "sqi": 91,
         "delta_f": {"wood": -0.05, "fire": -0.44, "earth": -0.18, "metal": -0.03, "water": -0.55},
         "v_obs": {"wood": 48.8, "fire": 32.1, "earth": 42.2, "metal": 49.2, "water": 29.1},
         "syndrome_hint": "火形分量下降明显"},
        {"date": "2026-09-08", "sqi": 79,
         "delta_f": {"wood": -0.07, "fire": -0.35, "earth": -0.14, "metal": -0.06, "water": -0.52},
         "v_obs": {"wood": 46.5, "fire": 37.2, "earth": 44.8, "metal": 46.9, "water": 30.5},
         "syndrome_hint": "第一次观测，基线建立"},
        {"date": "2026-09-05", "sqi": 85,
         "delta_f": {"wood": -0.04, "fire": -0.32, "earth": -0.10, "metal": -0.02, "water": -0.50},
         "v_obs": {"wood": 49.2, "fire": 38.5, "earth": 46.1, "metal": 49.8, "water": 31.2},
         "syndrome_hint": "基线"},
        {"date": "2026-08-02", "sqi": 88,
         "delta_f": {"wood": -0.03, "fire": -0.28, "earth": -0.08, "metal": -0.01, "water": -0.45},
         "v_obs": {"wood": 50.1, "fire": 40.2, "earth": 47.3, "metal": 50.5, "water": 33.8},
         "syndrome_hint": "出生事件校核，先天基底确认"},
        {"date": "2026-07-18", "sqi": 90,
         "delta_f": {"wood": -0.02, "fire": -0.25, "earth": -0.06, "metal": -0.01, "water": -0.42},
         "v_obs": {"wood": 51.0, "fire": 41.8, "earth": 48.5, "metal": 50.8, "water": 35.2},
         "syndrome_hint": "重要发现：木形基线比预期高"},
        {"date": "2026-07-01", "sqi": 76,
         "delta_f": {"wood": -0.01, "fire": -0.22, "earth": -0.05, "metal": 0.00, "water": -0.40},
         "v_obs": {"wood": 52.0, "fire": 43.1, "earth": 49.5, "metal": 51.2, "water": 36.0},
         "syndrome_hint": "第一次 PPG 观测"},
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
