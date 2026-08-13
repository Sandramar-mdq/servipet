import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.cliente_otp import ClienteOTP

OTP_EXPIRACION_MINUTOS = 5
OTP_MAX_INTENTOS = 3


def generar_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(codigo: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", codigo.encode(), salt, 100_000)
    return f"{salt.hex()}${digest.hex()}"


def verificar_hash_otp(codigo: str, codigo_hash: str) -> bool:
    try:
        salt_hex, digest_hex = codigo_hash.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", codigo.encode(), salt, 100_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def enviar_otp_mock(telefono: str, codigo: str) -> None:
    print(f"[MOCK OTP] Enviando codigo {codigo} al telefono {telefono}")


def crear_otp(db: Session, telefono: str) -> str:
    previos = (
        db.query(ClienteOTP)
        .filter(ClienteOTP.telefono == telefono, ClienteOTP.usado == False)
        .all()
    )
    for otp in previos:
        otp.usado = True

    codigo = generar_otp()
    ahora = datetime.utcnow()
    registro = ClienteOTP(
        telefono=telefono,
        codigo_hash=hash_otp(codigo),
        creado_en=ahora,
        expira_en=ahora + timedelta(minutes=OTP_EXPIRACION_MINUTOS),
        intentos=0,
        usado=False,
    )
    db.add(registro)
    db.commit()
    enviar_otp_mock(telefono, codigo)
    return codigo


def validar_otp(db: Session, telefono: str, codigo: str) -> tuple[bool, str]:
    otp = (
        db.query(ClienteOTP)
        .filter(ClienteOTP.telefono == telefono, ClienteOTP.usado == False)
        .order_by(ClienteOTP.creado_en.desc())
        .first()
    )
    if not otp:
        return False, "No hay un codigo pendiente para este telefono"

    ahora = datetime.utcnow()
    if otp.expira_en < ahora:
        otp.usado = True
        db.commit()
        return False, "El codigo expiro, solicita uno nuevo"

    if otp.intentos >= OTP_MAX_INTENTOS:
        otp.usado = True
        db.commit()
        return False, "Demasiados intentos, solicita un nuevo codigo"

    if not verificar_hash_otp(codigo.strip(), otp.codigo_hash):
        otp.intentos += 1
        db.commit()
        restantes = OTP_MAX_INTENTOS - otp.intentos
        if restantes <= 0:
            otp.usado = True
            db.commit()
            return False, "Codigo incorrecto, solicita uno nuevo"
        return False, f"Codigo incorrecto, intentos restantes: {restantes}"

    otp.usado = True
    db.commit()
    return True, "ok"
