"""
app/config.py — Configuración de la aplicación.

Lee el archivo .env con la stdlib pura (sin python-dotenv ni pydantic).
Expone las rutas importantes y la clave maestra de cifrado.
"""

import os
from pathlib import Path


def _find_project_root() -> Path:
    """
    Determina el directorio raíz donde se guardan .env y ciphie.db.

    Orden de precedencia:
    1. Variable de entorno CIPHIE_HOME (ruta personalizada)
    2. Directorio de trabajo actual, si contiene un .env (modo dev / backward compat)
    3. ~/.ciphie/ (modo instalado con pip install)
    """
    if os.environ.get("CIPHIE_HOME"):
        return Path(os.environ["CIPHIE_HOME"]).expanduser().resolve()
    cwd = Path.cwd()
    if (cwd / ".env").exists():
        return cwd
    # En modo instalado, el .env y la BD van en ~/.ciphie/
    default = Path.home() / ".ciphie"
    default.mkdir(exist_ok=True)
    return default


PROJECT_ROOT = _find_project_root()
_ENV_FILE    = PROJECT_ROOT / ".env"
DB_PATH      = PROJECT_ROOT / "ciphie.db"


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
        valor = valor.split("#")[0].strip()  # eliminar comentarios inline
        os.environ.setdefault(clave.strip(), valor)


# Cargamos el .env al importar este módulo
_cargar_env()


def get_smtp_config() -> dict:
    """Devuelve la configuración SMTP del .env para enviar emails."""
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", ""),
        "pass": os.environ.get("SMTP_PASS", ""),
    }


def get_twilio_config() -> dict:
    """Devuelve la configuración Twilio del .env para enviar SMS."""
    return {
        "account_sid":  os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "auth_token":   os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "from_number":  os.environ.get("TWILIO_FROM_NUMBER", ""),
    }


def get_master_key() -> bytes:
    """
    Devuelve la clave maestra de cifrado como bytes.
    Lanza RuntimeError si la variable no está configurada.
    """
    clave = os.environ.get("MASTER_ENCRYPTION_KEY", "")
    if not clave:
        raise RuntimeError(
            "MASTER_ENCRYPTION_KEY no está configurada.\n"
            f"Edita el archivo {_ENV_FILE} y anade la clave.\n"
            "Genera una con: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return clave.encode("utf-8")
