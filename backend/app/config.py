"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TRIAM CRM"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://crm_user:crm_password@localhost:5432/prognica_crm"

    # JWT Auth
    JWT_SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_REFRESH_SECRET_KEY: str = "change-me-refresh-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — add your Railway frontend URL here via CORS_ORIGINS env var
    # e.g. CORS_ORIGINS=["https://your-frontend.railway.app","http://localhost:3000"]
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    # Convenience: set CORS_ALLOW_ALL=true on Railway to allow all origins during demo
    CORS_ALLOW_ALL: bool = False

    # SMTP / notification email (existing org mailbox — no paid SaaS notification service)
    SMTP_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@ezeetechgroup.com"
    SMTP_FROM_NAME: str = "TRIAM"
    SMTP_USE_TLS: bool = True

    # Compliance cadence (configurable per the DIFC filing calendar)
    RENEWAL_CADENCE_MONTHS: int = 12
    COMPLIANCE_FILING_CADENCE_MONTHS: int = 12
    TAX_FILING_CADENCE_MONTHS: int = 12

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
