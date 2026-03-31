"""
app/auth.py — Registro e inicio de sesion de usuarios.

Usa hashlib.pbkdf2_hmac (stdlib) para el hashing de contrasenas.
PBKDF2-HMAC-SHA256 aplica la funcion de hash miles de veces, haciendo
los ataques de fuerza bruta lentos sin requerir paquetes externos.

Por que PBKDF2 y no SHA-256 directo?
SHA-256 es rapido: un atacante puede probar miles de millones de contrasenas
por segundo. PBKDF2 repite el hash 310.000 veces (recomendacion OWASP 2023),
haciendo los ataques inviables en tiempo razonable.
"""

import base64
import hashlib
import hmac
import logging
import os
import re
import random
import sqlite3
import ssl
import struct
import time as _tiempo
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText

_log = logging.getLogger(__name__)

from app.database import get_connection

# OTPs en memoria — se limpian al verificar o al expirar (5 min)
_otp_registro_pendientes: dict = {}   # verificación de cuenta nueva
_otp_2fa_pendientes: dict = {}        # 2FA en login (email o SMS)
_otp_intentos: dict = {}              # intentos fallidos por username (se resetea al verificar)


@dataclass
class Usuario:
    """Representa un usuario autenticado (sin contrasena)."""
    id: int
    username: str
    email: str
    is_active: bool


# ---------------------------------------------------------------------------
# Hashing de contrasenas
# ---------------------------------------------------------------------------

_ITERATIONS, _DKLEN = 310_000, 64


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    clave = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=_DKLEN
    )
    return salt.hex() + ":" + clave.hex()


def _verify_password(password: str, hashed: str) -> bool:
    try:
        salt_hex, clave_hex = hashed.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(clave_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=_DKLEN
        )
        return hmac.compare_digest(actual, esperado)
    except Exception as e:
        _log.warning("Hash corrupto al verificar contraseña: %s", e)
        return False


# ---------------------------------------------------------------------------
# Validaciones de entrada
# ---------------------------------------------------------------------------

def _validar_username(username: str) -> str:
    username = username.strip()
    if len(username) < 3:
        raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
    if not username.replace("_", "").isalnum():
        raise ValueError("El nombre de usuario solo puede tener letras, números y _")
    return username


def _validar_email(email: str) -> str:
    email = email.strip()
    partes = email.split("@")
    if len(partes) != 2 or not partes[0] or "." not in partes[1]:
        raise ValueError("El email no tiene un formato válido.")
    return email


def _validar_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError("La contrasena debe tener al menos 12 caracteres.")


def _validar_phone(phone: str) -> str:
    """Valida numero de celular. Acepta formato E.164 (+54911...) o local."""
    digitos = re.sub(r'[\s\-\(\)\.]', '', phone)
    if not re.match(r'^\+?\d{7,15}$', digitos):
        raise ValueError("El numero de celular no es valido (debe tener 7-15 digitos).")
    return phone.strip()


# ---------------------------------------------------------------------------
# Helpers OTP en memoria
# ---------------------------------------------------------------------------

def _guardar_otp(username: str, storage: dict, ttl: int = 300) -> str:
    """Genera un OTP de 6 dígitos, lo guarda en storage y lo devuelve."""
    codigo = f"{random.SystemRandom().randint(0, 999999):06d}"
    storage[username] = (codigo, _tiempo.time() + ttl)
    return codigo


_MAX_OTP_INTENTOS = 5


def _verificar_otp(username: str, codigo: str, storage: dict) -> bool:
    """Verifica el OTP. Lo elimina si es correcto, si expiró o si supera 5 intentos."""
    entrada = storage.get(username)
    if entrada is None:
        return False
    guardado, expira_en = entrada
    if _tiempo.time() > expira_en:
        del storage[username]
        _otp_intentos.pop(username, None)
        return False
    if hmac.compare_digest(guardado, codigo.strip()):
        del storage[username]
        _otp_intentos.pop(username, None)
        return True
    # Intento fallido: incrementar contador y bloquear si alcanza el límite
    _otp_intentos[username] = _otp_intentos.get(username, 0) + 1
    if _otp_intentos[username] >= _MAX_OTP_INTENTOS:
        del storage[username]
        _otp_intentos.pop(username, None)
    return False


# ---------------------------------------------------------------------------
# Envío de email
# ---------------------------------------------------------------------------

def _smtp_configurado() -> bool:
    """Devuelve True si SMTP esta configurado en .env."""
    from app.config import get_smtp_config
    cfg = get_smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["pass"])


def _enviar_email(to_email: str, subject: str, body: str) -> None:
    """Envia un email via SMTP. Lanza RuntimeError si no esta configurado."""
    import smtplib
    from app.config import get_smtp_config

    cfg = get_smtp_config()
    if not cfg["host"] or not cfg["user"]:
        raise RuntimeError(
            "SMTP no configurado. Agrega SMTP_HOST, SMTP_PORT, SMTP_USER y SMTP_PASS al .env\n"
            "Para Gmail usa una Contrasena de Aplicacion (no tu contrasena normal)."
        )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = cfg["user"]
    msg["To"] = to_email

    with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.login(cfg["user"], cfg["pass"])
        server.send_message(msg)


# ---------------------------------------------------------------------------
# Envío de SMS (Twilio REST API — sin SDK)
# ---------------------------------------------------------------------------

def _enviar_sms(to_phone: str, body: str) -> None:
    """Envía un SMS via Twilio REST API. Lanza RuntimeError si no está configurado."""
    from app.config import get_twilio_config

    cfg = get_twilio_config()
    if not all([cfg["account_sid"], cfg["auth_token"], cfg["from_number"]]):
        raise RuntimeError(
            "Twilio no configurado. Anade TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y "
            "TWILIO_FROM_NUMBER al .env"
        )
    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{cfg['account_sid']}/Messages.json"
    )
    credenciales = base64.b64encode(
        f"{cfg['account_sid']}:{cfg['auth_token']}".encode()
    ).decode()
    data = urllib.parse.urlencode({
        "From": cfg["from_number"],
        "To":   to_phone,
        "Body": body,
    }).encode()
    req = urllib.request.Request(url, data=data)
    req.add_header("Authorization", f"Basic {credenciales}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"Error SMS Twilio: HTTP {resp.status}")


# ---------------------------------------------------------------------------
# Registro de usuarios
# ---------------------------------------------------------------------------

def registrar_usuario(username: str, email: str, password: str, recovery_phrase: str) -> Usuario:
    """
    Crea un nuevo usuario en la base de datos (is_active=1).
    Usado por los tests y flujos que no requieren verificación por email.
    """
    username = _validar_username(username)
    email = _validar_email(email)
    _validar_password(password)
    if not recovery_phrase.strip():
        raise ValueError("La frase de recuperación no puede estar vacía.")

    hashed = _hash_password(password)
    hashed_frase = _hash_password(recovery_phrase.strip())

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, hashed_password, hashed_recovery_phrase) "
                "VALUES (?, ?, ?, ?)",
                (username, email, hashed, hashed_frase),
            )
            conn.commit()
            return Usuario(id=cursor.lastrowid, username=username, email=email, is_active=True)
    except sqlite3.IntegrityError as e:
        mensaje = str(e).lower()
        if "username" in mensaje:
            raise ValueError("El nombre de usuario ya está en uso.")
        if "email" in mensaje:
            raise ValueError("El email ya está registrado.")
        raise ValueError("Error al registrar el usuario.")


def iniciar_registro(
    username: str,
    email: str,
    password: str,
    recovery_phrase: str,
    phone: "str | None" = None,
) -> "tuple[str, bool]":
    """
    Crea un nuevo usuario y devuelve (username, needs_verification).

    - Si SMTP esta configurado: crea usuario inactivo (is_active=0), envia OTP por email
      y devuelve (username, True) para que la UI muestre pantalla de verificacion.
    - Si SMTP NO esta configurado: activa el usuario directamente (is_active=1)
      y devuelve (username, False) para que la UI vaya directo al login.
    """
    username = _validar_username(username)
    email = _validar_email(email)
    _validar_password(password)
    if not recovery_phrase.strip():
        raise ValueError("La frase de recuperacion no puede estar vacia.")
    phone_limpio = None
    if phone and phone.strip():
        phone_limpio = _validar_phone(phone)

    hashed = _hash_password(password)
    hashed_frase = _hash_password(recovery_phrase.strip())

    smtp_ok = _smtp_configurado()
    is_active_inicial = 0 if smtp_ok else 1

    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users "
                "(username, email, hashed_password, hashed_recovery_phrase, phone_number, is_active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, email, hashed, hashed_frase, phone_limpio, is_active_inicial),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        mensaje = str(e).lower()
        if "username" in mensaje:
            raise ValueError("El nombre de usuario ya esta en uso.")
        if "email" in mensaje:
            raise ValueError("El email ya esta registrado.")
        raise ValueError("Error al registrar el usuario.")

    if not smtp_ok:
        # Sin SMTP: cuenta activa directamente, sin verificacion por email
        return username, False

    # Con SMTP: generar y enviar OTP de verificacion
    codigo = _guardar_otp(username, _otp_registro_pendientes)
    _enviar_email(
        email,
        f"Ciphie - codigo de verificacion: {codigo}",
        f"Tu codigo de verificacion Ciphie es: {codigo}\n\n"
        "Expira en 5 minutos. No lo compartas con nadie.",
    )
    if phone_limpio:
        try:
            _enviar_sms(phone_limpio, f"Ciphie: tu codigo es {codigo}. Expira en 5 min.")
        except RuntimeError:
            pass  # SMS opcional — si Twilio no esta configurado, se ignora

    return username, True


def reenviar_otp_registro(username: str) -> None:
    """Reenvía el codigo de verificacion de registro."""
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT email, phone_number FROM users WHERE username=? AND is_active=0",
            (username,),
        ).fetchone()
    if fila is None:
        raise ValueError("Usuario no encontrado o ya verificado.")

    codigo = _guardar_otp(username, _otp_registro_pendientes)
    _enviar_email(
        fila["email"],
        f"Ciphie - codigo de verificacion: {codigo}",
        f"Tu codigo de verificacion Ciphie es: {codigo}\n\n"
        "Expira en 5 minutos. No lo compartas con nadie.",
    )
    if fila["phone_number"]:
        try:
            _enviar_sms(fila["phone_number"], f"Ciphie: tu codigo es {codigo}. Expira en 5 min.")
        except RuntimeError:
            pass


def verificar_otp_registro_y_activar(username: str, codigo: str) -> "Usuario | None":
    """Verifica el código de registro y activa la cuenta. Devuelve el Usuario o None."""
    if not _verificar_otp(username, codigo, _otp_registro_pendientes):
        return None
    with get_connection() as conn:
        conn.execute("UPDATE users SET is_active=1 WHERE username=?", (username,))
        conn.commit()
    return _obtener_usuario_activo(username)


def autenticar_usuario(username: str, password: str) -> "Usuario | None":
    """Verifica las credenciales. Devuelve Usuario o None."""
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT id, username, email, hashed_password, is_active "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if fila is None:
        return None
    if not fila["is_active"]:
        return None
    if not _verify_password(password, fila["hashed_password"]):
        return None

    return Usuario(
        id=fila["id"],
        username=fila["username"],
        email=fila["email"],
        is_active=True,
    )


# ---------------------------------------------------------------------------
# 2FA — TOTP (RFC 6238, compatible con Google Authenticator / Authy)
# ---------------------------------------------------------------------------

def generar_secreto_totp() -> str:
    return base64.b32encode(os.urandom(20)).decode("utf-8")


def uri_totp(username: str, secreto_b32: str) -> str:
    from urllib.parse import quote
    return (
        f"otpauth://totp/Ciphie:{quote(username)}"
        f"?secret={secreto_b32}&issuer=Ciphie"
    )


def _hotp(secreto_b32: str, contador: int) -> int:
    clave = base64.b32decode(secreto_b32.upper())
    msg = struct.pack(">Q", contador)
    digest = hmac.new(clave, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    codigo = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return codigo % 1_000_000


def verificar_totp(secreto_b32: str, codigo: str) -> bool:
    try:
        t = int(_tiempo.time()) // 30
        valor = int(codigo.strip())
        return any(_hotp(secreto_b32, t + d) == valor for d in (-1, 0, 1))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 2FA — OTP en login (email o SMS, elección en tiempo real)
# ---------------------------------------------------------------------------

def get_metodos_2fa_disponibles(username: str) -> list:
    """
    Devuelve los metodos de 2FA disponibles para el usuario:
      'email'      — si SMTP esta configurado
      'phone'      — si el usuario tiene phone_number y Twilio esta configurado
      'totp_app'   — si el usuario tiene secreto TOTP activo
      'biometrico' — si el metodo configurado es biometrico (Touch ID/huella)
    """
    from app.config import get_smtp_config, get_twilio_config

    with get_connection() as conn:
        fila = conn.execute(
            "SELECT totp_enabled, totp_method, totp_secret, phone_number "
            "FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if fila is None:
        return []

    metodos = []
    smtp = get_smtp_config()
    if smtp["host"] and smtp["user"]:
        metodos.append("email")

    twilio = get_twilio_config()
    if fila["phone_number"] and all(
        [twilio["account_sid"], twilio["auth_token"], twilio["from_number"]]
    ):
        metodos.append("phone")

    if fila["totp_enabled"] and fila["totp_method"] == "app" and fila["totp_secret"]:
        metodos.append("totp_app")

    if fila["totp_enabled"] and fila["totp_method"] == "biometrico":
        metodos.append("biometrico")

    return metodos


def generar_otp_2fa_email(username: str) -> None:
    """Genera y envia OTP de 2FA por email."""
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT email FROM users WHERE username=?", (username,)
        ).fetchone()
    if fila is None:
        raise ValueError("Usuario no encontrado.")
    codigo = _guardar_otp(username, _otp_2fa_pendientes)
    _enviar_email(
        fila["email"],
        f"Ciphie - codigo de acceso: {codigo}",
        f"Tu codigo de verificacion Ciphie es: {codigo}\n\n"
        "Expira en 5 minutos. No lo compartas con nadie.",
    )


def generar_otp_2fa_phone(username: str) -> None:
    """Genera y envía OTP de 2FA por SMS."""
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT phone_number FROM users WHERE username=?", (username,)
        ).fetchone()
    if fila is None or not fila["phone_number"]:
        raise ValueError("El usuario no tiene número de celular configurado.")
    codigo = _guardar_otp(username, _otp_2fa_pendientes)
    _enviar_sms(fila["phone_number"], f"Ciphie: tu código es {codigo}. Expira en 5 min.")


def verificar_otp_2fa(username: str, codigo: str) -> bool:
    """Verifica el OTP de 2FA (email o SMS)."""
    return _verificar_otp(username, codigo, _otp_2fa_pendientes)


# ---------------------------------------------------------------------------
# 2FA — Gestión en BD
# ---------------------------------------------------------------------------

def obtener_config_2fa(username: str) -> "dict | None":
    from app.crypto import descifrar
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT id, totp_enabled, totp_method, totp_secret, email, phone_number "
            "FROM users WHERE username=?",
            (username,),
        ).fetchone()
    if fila is None:
        return None
    secreto_raw = fila["totp_secret"]
    secreto = None
    if secreto_raw:
        try:
            secreto = descifrar(secreto_raw)
        except Exception:
            secreto = secreto_raw  # fallback para secretos en plaintext no migrados
    return {
        "user_id":      fila["id"],
        "enabled":      bool(fila["totp_enabled"]),
        "method":       fila["totp_method"],
        "secret":       secreto,
        "email":        fila["email"],
        "phone_number": fila["phone_number"],
    }


def activar_2fa(user_id: int, method: str, totp_secret: "str | None" = None) -> None:
    from app.crypto import cifrar
    secret_cifrado = cifrar(totp_secret) if totp_secret else None
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET totp_enabled=1, totp_method=?, totp_secret=? WHERE id=?",
            (method, secret_cifrado, user_id),
        )
        conn.commit()


def desactivar_2fa(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET totp_enabled=0, totp_method=NULL, totp_secret=NULL WHERE id=?",
            (user_id,),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Login en 2 pasos
# ---------------------------------------------------------------------------

_MAX_LOGIN_INTENTOS = 5
_LOCKOUT_MINUTOS = 15


def autenticar_paso1(username: str, password: str) -> "tuple[str, Usuario | None]":
    """
    Primer paso: verifica usuario y contrasena.

    Retorna:
        ('ok',            usuario) — sin 2FA, login completo
        ('2fa_requerido', None)    — credenciales ok, ir a pantalla de elección de método
        ('fallo',         None)    — credenciales incorrectas o cuenta inactiva
        ('bloqueado',     None)    — cuenta bloqueada por demasiados intentos fallidos
    """
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT id, username, email, hashed_password, is_active, totp_enabled, "
            "failed_login_attempts, locked_until "
            "FROM users WHERE username=?",
            (username,),
        ).fetchone()

    if fila is None or not fila["is_active"]:
        return ("fallo", None)

    # Verificar bloqueo por intentos fallidos
    if fila["locked_until"]:
        if datetime.now().isoformat() < fila["locked_until"]:
            return ("bloqueado", None)
        # Bloqueo expirado: limpiar
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE username=?",
                (username,),
            )
            conn.commit()

    if not _verify_password(password, fila["hashed_password"]):
        nuevos_intentos = (fila["failed_login_attempts"] or 0) + 1
        if nuevos_intentos >= _MAX_LOGIN_INTENTOS:
            bloqueado_hasta = (datetime.now() + timedelta(minutes=_LOCKOUT_MINUTOS)).isoformat()
            with get_connection() as conn:
                conn.execute(
                    "UPDATE users SET failed_login_attempts=?, locked_until=? WHERE username=?",
                    (nuevos_intentos, bloqueado_hasta, username),
                )
                conn.commit()
        else:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE users SET failed_login_attempts=? WHERE username=?",
                    (nuevos_intentos, username),
                )
                conn.commit()
        return ("fallo", None)

    # Credenciales correctas: resetear contador
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET failed_login_attempts=0, locked_until=NULL WHERE username=?",
            (username,),
        )
        conn.commit()

    if not fila["totp_enabled"]:
        usuario = Usuario(
            id=fila["id"], username=fila["username"],
            email=fila["email"], is_active=True,
        )
        return ("ok", usuario)

    return ("2fa_requerido", None)


def _obtener_usuario_activo(username: str) -> "Usuario | None":
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT id, username, email FROM users WHERE username=? AND is_active=1",
            (username,),
        ).fetchone()
    if fila is None:
        return None
    return Usuario(id=fila["id"], username=fila["username"], email=fila["email"], is_active=True)


def autenticar_paso2_generico(username: str, codigo: str) -> "Usuario | None":
    """Paso 2 con OTP de _otp_2fa_pendientes (email o SMS)."""
    if not verificar_otp_2fa(username, codigo):
        return None
    return _obtener_usuario_activo(username)


def autenticar_paso2_totp(username: str, codigo: str) -> "Usuario | None":
    """Paso 2 con código TOTP de app autenticadora."""
    cfg = obtener_config_2fa(username)
    if cfg is None or not cfg["enabled"] or cfg["method"] != "app":
        return None
    if not verificar_totp(cfg["secret"], codigo):
        return None
    return _obtener_usuario_activo(username)


# ---------------------------------------------------------------------------
# Edicion de perfil de usuario
# ---------------------------------------------------------------------------

def actualizar_usuario(user_id: int, new_username: str = None, new_email: str = None) -> None:
    """Actualiza username y/o email. Lanza ValueError si ya estan en uso."""
    updates: list[str] = []
    params: list = []
    if new_username:
        new_username = _validar_username(new_username)
        updates.append("username = ?")
        params.append(new_username)
    if new_email:
        new_email = _validar_email(new_email)
        updates.append("email = ?")
        params.append(new_email)
    if not updates:
        return
    params.append(user_id)
    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        msg = str(e).lower()
        if "username" in msg:
            raise ValueError("El nombre de usuario ya esta en uso.")
        if "email" in msg:
            raise ValueError("El email ya esta registrado.")
        raise ValueError("Error al actualizar el usuario.")


