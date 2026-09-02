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
    NOTIFICATION_WEBHOOK_URL: str | None = None
    NOTIFICATION_WEBHOOK_TIMEOUT_S: int = 10
    NOTIFICATION_MAX_INTENTOS: int = 3
    TURSO_AUTH_TOKEN: str | None = None

    # Cloudinary (red comunitaria - fotos de avisos)
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = None

    # Chatbot IA (Etapa 9.1 - Gemini API)
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TIMEOUT_S: int = 15

    # JWT settings
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 días

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
