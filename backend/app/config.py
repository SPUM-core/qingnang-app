"""青囊后端配置 - 从环境变量或 .env 读取（敏感项必填，禁止硬编码默认值）"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # 服务
    APP_NAME: str = "青囊后端 · Qingnang Backend"
    VERSION: str = "0.1.0"
    APP_ENV: str = "development"   # development / production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # 数据库连接串（必填，从环境变量 / .env 注入，如
    # postgresql+psycopg2://qingnang:xxx@localhost:5432/qingnang）
    DATABASE_URL: str

    # JWT 签名密钥（必填，64 位随机 hex，禁止硬编码默认值）
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_HOURS: int = 72

    # ── LLM：全局只用 DeepSeek 云端（本地 Ollama 模型已下线） ──
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ── 青檬引擎：仅用于确定性推理（bazi / daily_brief / lifestyle） ──
    # LLM 能力已切走，不再调它的 /v1/chat/completions
    QINGMENG_URL: str = "http://localhost:8000"

    # CORS 白名单（JSON 数组字符串，从环境变量注入）
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 种子数据自动注入（默认关闭；阶段0 后以迁移 + 业务数据为准）
    AUTO_SEED: bool = False

    # ── APP 自动更新推送 ──
    # 更新文件托管根目录（后端静态文件服务路径）
    APP_UPDATE_DIR: str = "updates"
    # APK / bundle 下载基础 URL（生产环境需配置 CDN 或完整域名）
    APP_UPDATE_BASE_URL: str = "http://localhost:8767/updates"
    # 是否启用 APP 更新检查（开发期可关）
    APP_UPDATE_ENABLED: bool = True

settings = Settings()
# （resolve_default_provider 已删除 — 全局只用 deepseek）
