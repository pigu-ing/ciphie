"""
app/database.py — Base de datos con sqlite3 (stdlib).
"""

import os
import sqlite3
import stat
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from app.config import DB_PATH


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def inicializar_bd() -> None:
    with get_connection() as conn:
        # ── Tabla users ──────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                username               TEXT    UNIQUE NOT NULL,
                email                  TEXT    UNIQUE NOT NULL,
                hashed_password        TEXT    NOT NULL,
                hashed_recovery_phrase TEXT,
                totp_enabled           INTEGER NOT NULL DEFAULT 0,
                totp_method            TEXT,
                totp_secret            TEXT,
                is_active              INTEGER NOT NULL DEFAULT 1,
                created_at             TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        for columna, definicion in [
            ("hashed_recovery_phrase",  "TEXT"),
            ("totp_enabled",            "INTEGER NOT NULL DEFAULT 0"),
            ("totp_method",             "TEXT"),
            ("totp_secret",             "TEXT"),
            ("phone_number",            "TEXT"),
            ("failed_login_attempts",   "INTEGER NOT NULL DEFAULT 0"),
            ("locked_until",            "TEXT"),
            ("lockout_minutes",         "INTEGER NOT NULL DEFAULT 5"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {columna} {definicion}")
            except sqlite3.OperationalError:
                pass  # columna ya existe

        # ── Tabla secrets ─────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS secrets (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL,
                encrypted_value  TEXT    NOT NULL,
                owner_id         INTEGER NOT NULL REFERENCES users(id),
                category         TEXT    NOT NULL DEFAULT 'otro',
                expires_at       TEXT,
                created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        for columna, definicion in [
            ("category",   "TEXT NOT NULL DEFAULT 'otro'"),
            ("expires_at", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE secrets ADD COLUMN {columna} {definicion}")
            except sqlite3.OperationalError:
                pass  # columna ya existe

        # ── Tabla audit_log ───────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                action      TEXT    NOT NULL,
                secret_name TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

        # ── Tabla secret_versions ─────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS secret_versions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                secret_id       INTEGER NOT NULL REFERENCES secrets(id),
                encrypted_value TEXT    NOT NULL,
                changed_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)

        conn.commit()

    # Restringir permisos del archivo de BD a solo el propietario (0o600)
    db_file = Path(DB_PATH)
    if db_file.exists():
        os.chmod(db_file, stat.S_IRUSR | stat.S_IWUSR)

    # Migrar secretos TOTP de plaintext a cifrado (si los hay)
    try:
        from app.crypto import cifrar, descifrar
        with get_connection() as conn:
            filas = conn.execute(
                "SELECT id, totp_secret FROM users "
                "WHERE totp_enabled=1 AND totp_secret IS NOT NULL"
            ).fetchall()
            for fila in filas:
                try:
                    descifrar(fila["totp_secret"])  # ya cifrado, nada que hacer
                except Exception:
                    # plaintext → cifrar
                    conn.execute(
                        "UPDATE users SET totp_secret=? WHERE id=?",
                        (cifrar(fila["totp_secret"]), fila["id"]),
                    )
            conn.commit()
    except Exception:
        pass  # MASTER_ENCRYPTION_KEY no configurada o no hay secretos TOTP


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Secreto:
    id: int
    name: str
    encrypted_value: str
    owner_id: int
    category: str
    created_at: str
    expires_at: "str | None" = None


@dataclass
class AuditEntry:
    id: int
    user_id: int
    action: str
    secret_name: str
    timestamp: str


@dataclass
class SecretVersion:
    id: int
    secret_id: int
    encrypted_value: str
    changed_at: str


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

_COLS_SECRETO = "id, name, encrypted_value, owner_id, category, created_at, expires_at"


def _fila_a_secreto(fila) -> Secreto:
    return Secreto(**dict(fila))


# ---------------------------------------------------------------------------
# CRUD — Secretos
# ---------------------------------------------------------------------------

def listar_secretos(owner_id: int) -> list[Secreto]:
    with get_connection() as conn:
        filas = conn.execute(
            f"SELECT {_COLS_SECRETO} FROM secrets "
            "WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
    return [_fila_a_secreto(f) for f in filas]


def agregar_secreto(
    name: str,
    encrypted_value: str,
    owner_id: int,
    category: str = "otro",
    expires_at: "str | None" = None,
) -> Secreto:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO secrets (name, encrypted_value, owner_id, category, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, encrypted_value, owner_id, category, expires_at),
        )
        conn.commit()
        fila = conn.execute(
            f"SELECT {_COLS_SECRETO} FROM secrets WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _fila_a_secreto(fila)


def obtener_secreto(secreto_id: int, owner_id: int) -> "Secreto | None":
    with get_connection() as conn:
        fila = conn.execute(
            f"SELECT {_COLS_SECRETO} FROM secrets WHERE id = ? AND owner_id = ?",
            (secreto_id, owner_id),
        ).fetchone()
    return _fila_a_secreto(fila) if fila else None


def editar_secreto(
    secret_id: int,
    owner_id: int,
    new_encrypted_value: str,
    new_name: str,
    new_category: str,
    new_expires_at: "str | None" = None,
) -> bool:
    """
    Guarda el valor actual en secret_versions antes de sobreescribirlo.
    Devuelve True si el secreto existía y fue actualizado.
    """
    with get_connection() as conn:
        fila = conn.execute(
            "SELECT encrypted_value FROM secrets WHERE id = ? AND owner_id = ?",
            (secret_id, owner_id),
        ).fetchone()
        if fila is None:
            return False
        # Guardar versión anterior
        conn.execute(
            "INSERT INTO secret_versions (secret_id, encrypted_value) VALUES (?, ?)",
            (secret_id, fila["encrypted_value"]),
        )
        # Actualizar secreto
        conn.execute(
            "UPDATE secrets SET name=?, encrypted_value=?, category=?, expires_at=?, "
            "updated_at=datetime('now','localtime') WHERE id=? AND owner_id=?",
            (new_name, new_encrypted_value, new_category, new_expires_at, secret_id, owner_id),
        )
        conn.commit()
    return True


def eliminar_secreto(secreto_id: int, owner_id: int) -> None:
    with get_connection() as conn:
        # Verificar ownership antes de borrar
        ok = conn.execute(
            "SELECT id FROM secrets WHERE id = ? AND owner_id = ?",
            (secreto_id, owner_id),
        ).fetchone()
        if ok is None:
            return
        # Borrar versiones primero (FK constraint)
        conn.execute("DELETE FROM secret_versions WHERE secret_id = ?", (secreto_id,))
        conn.execute(
            "DELETE FROM secrets WHERE id = ? AND owner_id = ?",
            (secreto_id, owner_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# CRUD — Versionado
# ---------------------------------------------------------------------------

def listar_versiones(secret_id: int, owner_id: int) -> list[SecretVersion]:
    """Devuelve las versiones anteriores del secreto, más reciente primero."""
    with get_connection() as conn:
        # Verificar ownership
        ok = conn.execute(
            "SELECT id FROM secrets WHERE id = ? AND owner_id = ?",
            (secret_id, owner_id),
        ).fetchone()
        if ok is None:
            return []
        filas = conn.execute(
            "SELECT id, secret_id, encrypted_value, changed_at "
            "FROM secret_versions WHERE secret_id = ? ORDER BY id DESC",
            (secret_id,),
        ).fetchall()
    return [SecretVersion(**dict(f)) for f in filas]


def restaurar_version(version_id: int, secret_id: int, owner_id: int) -> bool:
    """
    Restaura el valor de una versión anterior.
    Guarda el valor actual como nueva versión antes de restaurar
    para que la operación sea reversible.
    Devuelve True si tuvo éxito.
    """
    with get_connection() as conn:
        secreto = conn.execute(
            "SELECT encrypted_value FROM secrets WHERE id = ? AND owner_id = ?",
            (secret_id, owner_id),
        ).fetchone()
        if secreto is None:
            return False
        version = conn.execute(
            "SELECT encrypted_value FROM secret_versions WHERE id = ? AND secret_id = ?",
            (version_id, secret_id),
        ).fetchone()
        if version is None:
            return False
        # Guardar valor actual como versión nueva (permite deshacer el restore)
        conn.execute(
            "INSERT INTO secret_versions (secret_id, encrypted_value) VALUES (?, ?)",
            (secret_id, secreto["encrypted_value"]),
        )
        # Restaurar
        conn.execute(
            "UPDATE secrets SET encrypted_value=?, updated_at=datetime('now','localtime') "
            "WHERE id=? AND owner_id=?",
            (version["encrypted_value"], secret_id, owner_id),
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# CRUD — Auditoría
# ---------------------------------------------------------------------------

def registrar_auditoria(user_id: int, action: str, secret_name: str) -> None:
    """Registra una acción del usuario en el audit_log."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, action, secret_name) VALUES (?, ?, ?)",
            (user_id, action, secret_name),
        )
        conn.commit()


def listar_auditoria(user_id: int, limite: int = 200) -> list[AuditEntry]:
    """Devuelve el historial de acciones del usuario, más reciente primero."""
    with get_connection() as conn:
        filas = conn.execute(
            "SELECT id, user_id, action, secret_name, timestamp "
            "FROM audit_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limite),
        ).fetchall()
    return [AuditEntry(**dict(f)) for f in filas]


# ---------------------------------------------------------------------------
# Consultas de usuarios
# ---------------------------------------------------------------------------

@dataclass
class UsuarioBasico:
    id: int
    username: str
    email: str


def listar_usuarios_basico() -> list[UsuarioBasico]:
    """Devuelve id, username y email de todos los usuarios activos."""
    with get_connection() as conn:
        filas = conn.execute(
            "SELECT id, username, email FROM users WHERE is_active = 1 ORDER BY username"
        ).fetchall()
    return [UsuarioBasico(**dict(f)) for f in filas]


# ---------------------------------------------------------------------------
# Consultas de expiración
# ---------------------------------------------------------------------------

def secretos_vencidos(owner_id: int) -> list[Secreto]:
    """Secretos cuyo expires_at ya pasó."""
    ahora = datetime.now().isoformat()
    with get_connection() as conn:
        filas = conn.execute(
            f"SELECT {_COLS_SECRETO} FROM secrets "
            "WHERE owner_id=? AND expires_at IS NOT NULL AND expires_at <= ?",
            (owner_id, ahora),
        ).fetchall()
    return [_fila_a_secreto(f) for f in filas]


def secretos_por_vencer(owner_id: int, dias: int = 7) -> list[Secreto]:
    """Secretos que vencen dentro de los próximos `dias` días (sin incluir los ya vencidos)."""
    ahora = datetime.now().isoformat()
    limite = (datetime.now() + timedelta(days=dias)).isoformat()
    with get_connection() as conn:
        filas = conn.execute(
            f"SELECT {_COLS_SECRETO} FROM secrets "
            "WHERE owner_id=? AND expires_at IS NOT NULL "
            "AND expires_at > ? AND expires_at <= ?",
            (owner_id, ahora, limite),
        ).fetchall()
    return [_fila_a_secreto(f) for f in filas]
