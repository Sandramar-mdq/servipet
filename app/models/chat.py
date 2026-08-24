from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatSesion(Base):
    """Sesion de conversacion con el asistente IA (Etapa 9.1).

    - Pertenece a un comercio (tenant) y a un actor autenticado
      ('usuario' con JWT o 'cliente' de la PWA) identificado por actor_id.
    - El par (actor_tipo, actor_id) se valida en cada request para evitar
      que un actor use sesiones ajenas.
    """

    __tablename__ = "chat_sesiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int] = mapped_column(Integer, ForeignKey("comercios.id"), nullable=False, index=True)
    actor_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ultimo_mensaje_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    mensajes: Mapped[list["ChatMensaje"]] = relationship(
        "ChatMensaje", back_populates="sesion", cascade="all, delete-orphan"
    )


class ChatMensaje(Base):
    """Mensaje individual dentro de una sesion de chat.

    - rol: 'user' (mensaje del actor) o 'model' (respuesta del asistente).
    - herramientas_usadas: JSON serializado con los nombres de las tools
      de function calling que Gemini invoco para generar esa respuesta.
    """

    __tablename__ = "chat_mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sesion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_sesiones.id"), nullable=False, index=True
    )
    rol: Mapped[str] = mapped_column(String(10), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    herramientas_usadas: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    sesion: Mapped["ChatSesion"] = relationship("ChatSesion", back_populates="mensajes")
