"""
app/auth.py — Registro e inicio de sesión de usuarios.

Usa hashlib.scrypt (stdlib, Python 3.6+) para el hashing de contraseñas.
scrypt es más seguro que bcrypt en cuanto a resistencia a ataques de hardware
y no requiere ningún paquete externo.

¿Por qué scrypt y no SHA-256?
SHA-256 es rápido: un atacante puede probar miles de millones de contraseñas
por segundo. scrypt es lento y consume mucha RAM a propósito, haciendo los
ataques de fuerza bruta inviables.
"""

import hashlib
import hmac
import os
import sqlite3
from dataclasses import dataclass

from app.database import get_connection


@dataclass
class Usuario:
    """Representa un usuario autenticado (sin contraseña)."""
    id: int
    username: str
    email: str
    is_active: bool


# ---------------------------------------------------------------------------
# Hashing de contraseñas
# ---------------------------------------------------------------------------

# Parámetros de scrypt (ajustados para escritorio):
# n=2^14 → coste de CPU/memoria. Cada aumento de 1 bit duplica el tiempo.
# r=8    → tamaño de bloque
# p=1    → paralelismo
# dklen=64 → tamaño de la clave derivada (64 bytes = 512 bits)
_N, _R, _P, _DKLEN = 2**14, 8, 1, 64


def _hash_password(password: str) -> str:
    """
    Genera un hash scrypt de la contraseña.
    Formato devuelto: "salt_hex:hash_hex"
    El salt es aleatorio (16 bytes) y se guarda junto al hash.
    """
    salt = os.urandom(16)
    clave = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
    )
    return salt.hex() + ":" + clave.hex()


def _verify_password(password: str, hashed: str) -> bool:
    """
    Comprueba si una contraseña coincide con su hash.
    Usa hmac.compare_digest para evitar ataques de timing.
    """
    try:
        salt_hex, clave_hex = hashed.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        esperado = bytes.fromhex(clave_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
        )
        # compare_digest compara en tiempo constante, sin filtrar info por timing
        return hmac.compare_digest(actual, esperado)
    except Exception:
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
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")


# ---------------------------------------------------------------------------
# Operaciones de usuario
# ---------------------------------------------------------------------------

def registrar_usuario(username: str, email: str, password: str) -> Usuario:
    """
    Crea un nuevo usuario en la base de datos.
    Lanza ValueError si los datos son inválidos o si el usuario/email ya existe.
    """
    username = _validar_username(username)
    email = _validar_email(email)
    _validar_password(password)

    hashed = _hash_password(password)

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
                (username, email, hashed),
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


def autenticar_usuario(username: str, password: str) -> Usuario | None:
    """
    Verifica las credenciales de un usuario.
    Devuelve el objeto Usuario si son correctas, None si no lo son.

    IMPORTANTE: devolver None en ambos casos (usuario no existe O contraseña
    incorrecta) evita revelar qué usuarios existen en el sistema.
    """
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT id, username, email, hashed_password, is_active "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if fila is None:
        return None
    if not _verify_password(password, fila["hashed_password"]):
        return None

    return Usuario(
        id=fila["id"],
        username=fila["username"],
        email=fila["email"],
        is_active=bool(fila["is_active"]),
    )
