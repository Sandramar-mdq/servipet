from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Clave de firma JWT del repo. Sirve unicamente para desarrollo local con
# DEBUG=true; con DEBUG=false la app se niega a arrancar si la detecta
# (ver `_validar_configuracion`).
SECRET_KEY_DEV = "dev-secret-cambiar-en-produccion"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./servipet.db"
    APP_NAME: str = "Servipet"
    DEBUG: bool = False
    SECRET_KEY: str = SECRET_KEY_DEV

    # Origenes CORS permitidos, separados por coma. Vacio es valido solo con
    # DEBUG=true: el front (Jinja + JS vanilla) se sirve desde la misma app, asi
    # que no hay peticiones cross-origin y no hace falta declarar nada. Con
    # DEBUG=false la app se niega a arrancar si queda vacio, para no exponer
    # accidentalmente un `allow_origins=["*"]` en produccion.
    CORS_ORIGINS: str = ""

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

    # Kit de Marketing B2B (Etapa 12) - TTF opcional para las placas PNG.
    # Si no se define, pieza_service busca fuentes del sistema y cae a
    # ImageFont.load_default(size=...).
    SERVIPET_FUENTE_PATH: str | None = None

    # extra="ignore": tolera claves ajenas a Settings en .env (ADMIN_*,
    # ALPHA_* son leidas por scripts/seed_alpha.py via os.environ, no por
    # pydantic-settings). Sin esto, pydantic-settings >= 2.14 levanta
    # ValidationError(extra_forbidden) con un .env que incluya esas claves.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Lista de origenes CORS efectiva.

        Con DEBUG=true devuelve ["*"] para no frenar el desarrollo local. Con
        DEBUG=false devuelve solo lo declarado en CORS_ORIGINS.
        """
        if self.DEBUG:
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validar_configuracion(self) -> "Settings":
        """Impide arrancar en produccion con configuracion insegura.

        Levanta ValidationError al construir Settings (app/config.py es un
        singleton a nivel de modulo), o sea antes de que uvicorn abra el
        socket. Falla fuerte y temprano en lugar de emitir JWT firmados con una
        clave publica del repo.
        """
        if self.DEBUG:
            return self

        if self.SECRET_KEY == SECRET_KEY_DEV:
            raise ValueError(
                "SECRET_KEY no puede ser el valor de desarrollo "
                f"({SECRET_KEY_DEV}) cuando DEBUG=false. Generar una con: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )

        if not self.CORS_ORIGINS.strip():
            raise ValueError(
                "CORS_ORIGINS no puede quedar vacio cuando DEBUG=false. "
                "Declarar los origenes separados por coma (por ejemplo "
                "https://servipet.onrender.com) o usar DEBUG=true en desarrollo."
            )

        return self


settings = Settings()