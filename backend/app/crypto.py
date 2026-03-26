"""
app/crypto.py — Cifrado y descifrado de secretos con Fernet.

Fernet usa AES-128-CBC + HMAC-SHA256. Es el único módulo que requiere
un paquete externo (`cryptography`) porque Python no incluye AES en su
biblioteca estándar.

¿Por qué Fernet y no AES manual?
Implementar cifrado correctamente es muy difícil. Fernet resuelve todos
los detalles (padding, IV aleatorio, autenticación del mensaje) de forma
segura y simple.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_master_key


def _get_fernet() -> Fernet:
    """Crea una instancia de Fernet con la clave maestra del .env."""
    return Fernet(get_master_key())


def cifrar(valor: str) -> str:
    """
    Cifra un texto plano y devuelve el resultado como string.
    Cada llamada produce un resultado diferente (Fernet incluye un IV aleatorio).
    """
    return _get_fernet().encrypt(valor.encode("utf-8")).decode("utf-8")


def descifrar(valor_cifrado: str) -> str:
    """
    Descifra un valor cifrado con Fernet.
    Lanza ValueError si la clave es incorrecta o los datos están corruptos.
    """
    try:
        return _get_fernet().decrypt(valor_cifrado.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError(
            "No se pudo descifrar el secreto. "
            "La clave maestra puede ser incorrecta o los datos están corruptos."
        )
