"""User + DoctorProfile"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float
from sqlalchemy.sql import func
from ..database import Base

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True)
    qingnang_id   = Column(String(32), unique=True, index=True)   # QN-xxxxxx

    # ── 登录标识（多 provider 预留）──────────────────────────────
    phone         = Column(String(20), unique=True, index=True)       # 手机号登录
    wechat_openid  = Column(String(64), unique=True, index=True)       # 微信小程序 openid
    wechat_unionid = Column(String(64), unique=True, index=True)      # 微信 unionid（跨应用统一身份）

    # ── 认证凭据 ──
    password_hash = Column(String(255))                               # bcrypt，微信用户可空

    # 基本资料
    nickname      = Column(String(50))
    gender        = Column(String(10))      # male / female / other
    birth_date    = Column(String(10))      # 1986-08-02
    birth_hour    = Column(String(10))      # 寅时（注意：这是**真太阳时**对应的时辰，不是北京时间）
    height        = Column(Integer)         # cm
    weight        = Column(Integer)         # kg
    city          = Column(String(20))      # 当前所在城市（用于查天气）

    # ⭐ 2026-10-08 新增：出生地经纬度（真太阳时校正必需）
    # 出生时柱 = 北京时间出生时 + (birth_longitude - 120) × 4 分钟
    birth_city    = Column(String(30))     # 出生地（如 "乌鲁木齐"）
    birth_longitude = Column(Float)          # 出生地经度（东经，如 87.62；西经为负）
    birth_latitude  = Column(Float)          # 出生地纬度（北纬为正，南纬为负）

    # 身份
    is_doctor     = Column(Boolean, default=False)   # 医生端
    is_onboarded  = Column(Boolean, default=False)   # 已完成初始化建档
    dev_seed      = Column(Boolean, default=False, server_default="false")  # 开发环境测试账号标记（迁移注入）
    is_member     = Column(Boolean, default=False, server_default="false")  # 会员：解锁 Stage 4 方剂级（隐藏功能）

    # 五形先天基底 S_0^0（出生时推导）
    v_base        = Column(JSON)             # {"wood": 70, "fire": 55, ...}

    # ⭐ 引导完成标记（前端 GuidesSeenPatch 持久化）
    guides_seen    = Column(JSON, default=dict, server_default='{}')

    # ⭐ 健康标签（onboarding / 问诊 / AI 自动提取）
    # {
    #   "chronic": ["hypertension", "diabetes", "hyperlipidemia"],  // 三高
    #   "allergies": ["花生", "青霉素"],
    #   "surgeries": ["阑尾切除术"],
    #   "conditions": ["慢性胃炎", "过敏性鼻炎"],
    #   "update_source": "onboarding" / "inquiry" / "ai_extract",
    #   "updated_at": "2026-10-06T10:00:00"
    # }
    health_tags   = Column(JSON, default=dict, server_default='{}')

    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())

class DoctorProfile(Base):
    """医生资质（仅 is_doctor=True 的用户有）"""
    __tablename__ = "doctor_profiles"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, unique=True, index=True)
    hospital      = Column(String(100))
    title         = Column(String(50))
    license_no    = Column(String(50))       # 执业医师资格证号
    license_img   = Column(String(255))       # 资质照片路径
    verified      = Column(Boolean, default=False)  # 平台审核
    verified_at   = Column(DateTime)
