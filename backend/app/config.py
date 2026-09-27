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

    # 青檬引擎（AI 对话）
    QINGMENG_URL: str = "http://localhost:8000"
    QINGMENG_MODEL: str = "spum-coder:latest"

    # CORS 白名单（JSON 数组字符串，从环境变量注入）
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 种子数据自动注入（默认关闭；阶段0 后以迁移 + 业务数据为准）
    AUTO_SEED: bool = False

settings = Settings()
