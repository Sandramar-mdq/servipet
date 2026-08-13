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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
