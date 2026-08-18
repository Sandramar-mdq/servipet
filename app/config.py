from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./servipet.db"
    APP_NAME: str = "Servipet"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-cambiar-en-produccion"
    NOTIFICATION_PROVIDER: str = "log"
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_FROM: str | None = None
    TURSO_AUTH_TOKEN: str | None = None

    # JWT settings
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
