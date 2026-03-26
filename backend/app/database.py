"""
app/database.py — Base de datos con sqlite3 (stdlib).

sqlite3 viene incluido en Python, no requiere instalación.
Este módulo se encarga de:
  1. Crear la conexión a la base de datos.
  2. Crear las tablas si no existen (al arrancar la app).
  3. Operaciones CRUD sobre la tabla `secrets`.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from app.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """
    Abre y devuelve una conexión a la base de datos.

    row_factory = sqlite3.Row permite acceder a las columnas por nombre
    (fila["username"]) en lugar de solo por índice (fila[0]).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Activa las claves foráneas (SQLite las ignora por defecto)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_bd() -> None:
    """
    Crea las tablas `users` y `secrets` si no existen.
    Se llama una vez al arrancar la aplicación.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                username         TEXT    UNIQUE NOT NULL,
                email            TEXT    UNIQUE NOT NULL,
                hashed_password  TEXT    NOT NULL,
                is_active        INTEGER NOT NULL DEFAULT 1,
                created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS secrets (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL,
                encrypted_value  TEXT    NOT NULL,
                owner_id         INTEGER NOT NULL REFERENCES users(id),
                created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Operaciones sobre secretos
# ---------------------------------------------------------------------------

@dataclass
class Secreto:
    id: int
    name: str
    encrypted_value: str
    owner_id: int
    created_at: str


def listar_secretos(owner_id: int) -> list[Secreto]:
    """Devuelve todos los secretos que pertenecen a un usuario."""
    with get_connection() as conn:
        filas = conn.execute(
            "SELECT id, name, encrypted_value, owner_id, created_at "
            "FROM secrets WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
    return [Secreto(**dict(fila)) for fila in filas]


def agregar_secreto(name: str, encrypted_value: str, owner_id: int) -> Secreto:
    """Guarda un nuevo secreto cifrado en la BD."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO secrets (name, encrypted_value, owner_id) VALUES (?, ?, ?)",
            (name, encrypted_value, owner_id),
        )
        conn.commit()
        fila = conn.execute(
            "SELECT id, name, encrypted_value, owner_id, created_at FROM secrets WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return Secreto(**dict(fila))


def eliminar_secreto(secreto_id: int, owner_id: int) -> None:
    """
    Elimina un secreto. Requiere el owner_id para evitar que un usuario
    borre secretos de otro usuario.
    """
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM secrets WHERE id = ? AND owner_id = ?",
            (secreto_id, owner_id),
        )
        conn.commit()
