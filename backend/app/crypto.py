"""
app/crypto.py — Cifrado y descifrado de secretos con AES-256-GCM.

AES-256-GCM es cifrado autenticado: garantiza confidencialidad e integridad
del mensaje con una clave de 256 bits (32 bytes) y un nonce aleatorio de 12 bytes.

Formato almacenado: base64url(nonce[12 bytes] + ciphertext+tag)
El tag de autenticación (16 bytes) va al final del ciphertext, incluido
automáticamente por AESGCM.
"""

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_master_key

# Salt fijo de aplicación para HKDF (no secreto, identifica el propósito)
_HKDF_SALT = b"ciphie-aes256-v1"


def _get_clave_aes() -> bytes:
    """Deriva una clave AES-256 de 32 bytes usando HKDF-SHA256."""
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=b"",
    ).derive(get_master_key())


def cifrar(valor: str) -> str:
    """
    Cifra un texto plano con AES-256-GCM y devuelve el resultado como string.
    Cada llamada produce un resultado diferente (nonce aleatorio de 12 bytes).
    """
    clave = _get_clave_aes()
    nonce = os.urandom(12)  # 96 bits — tamaño recomendado para GCM
    aesgcm = AESGCM(clave)
    cifrado = aesgcm.encrypt(nonce, valor.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + cifrado).decode("utf-8")


def descifrar(valor_cifrado: str) -> str:
    """
    Descifra un valor cifrado con AES-256-GCM.
    Lanza ValueError si la clave es incorrecta o los datos están corruptos.
    """
    try:
        datos = base64.urlsafe_b64decode(valor_cifrado.encode("utf-8"))
        nonce = datos[:12]
        cifrado = datos[12:]
        clave = _get_clave_aes()
        aesgcm = AESGCM(clave)
        return aesgcm.decrypt(nonce, cifrado, None).decode("utf-8")
    except Exception:
        raise ValueError(
            "No se pudo descifrar el secreto. "
            "La clave maestra puede ser incorrecta o los datos están corruptos."
        )
