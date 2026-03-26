"""
app/config.py — Configuración de la aplicación.

Lee el archivo .env con la stdlib pura (sin python-dotenv ni pydantic).
Expone las rutas importantes y la clave maestra de cifrado.
"""

import os
from pathlib import Path

# Raíz del proyecto (dos niveles arriba de este archivo: app/ → backend/ → ciphie/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Ruta al archivo .env
_ENV_FILE = PROJECT_ROOT / ".env"

# La base de datos se guarda en la raíz del proyecto
DB_PATH = PROJECT_ROOT / "ciphie.db"


def _cargar_env() -> None:
    """
    Lee el archivo .env línea por línea y carga cada variable en os.environ.
    Solo carga variables que aún no están definidas (setdefault).
    Ignora líneas vacías y comentarios (#).
    """
    if not _ENV_FILE.exists():
        return
    for linea in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip())


# Cargamos el .env al importar este módulo
_cargar_env()


def get_master_key() -> bytes:
    """
    Devuelve la clave maestra de cifrado como bytes.
    Fernet requiere bytes, no str.
    Lanza RuntimeError si la variable no está configurada.
    """
    clave = os.environ.get("MASTER_ENCRYPTION_KEY", "")
    if not clave:
        raise RuntimeError(
            "MASTER_ENCRYPTION_KEY no está configurada.\n"
            f"Edita el archivo {_ENV_FILE} y añade la clave.\n"
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return clave.encode("utf-8")
