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

    # 青檬引擎（AI 对话 · SPUM 本地模型）
    QINGMENG_URL: str = "http://localhost:8000"
    QINGMENG_MODEL: str = "spum-v9-thinking:latest"

    # DeepSeek（云端 LLM 备选 — 用户在设置里选择）
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # 默认 LLM provider：production 推荐 deepseek（无需本地青檬引擎）
    # 可选值: "spum"(青檬引擎), "deepseek"(云端), "auto"(自动：有API_KEY用deepseek)
    DEFAULT_PROVIDER: str = "auto"

    # CORS 白名单（JSON 数组字符串，从环境变量注入）
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 种子数据自动注入（默认关闭；阶段0 后以迁移 + 业务数据为准）
    AUTO_SEED: bool = False

settings = Settings()

def resolve_default_provider() -> str:
    """解析默认 provider：auto → 有 DEEPSEEK_API_KEY 就走 deepseek，否则 spum"""
    dp = settings.DEFAULT_PROVIDER.lower()
    if dp in ("spum", "deepseek", "ollama"):
        return dp
    if settings.DEEPSEEK_API_KEY:
        return "deepseek"
    return "spum"

settings.DEFAULT_PROVIDER_RESOLVED = resolve_default_provider()
