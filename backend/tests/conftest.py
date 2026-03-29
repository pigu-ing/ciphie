"""
tests/conftest.py — Configuración global de los tests.

Configura una base de datos temporal para cada test, de forma que
los tests no interfieran entre sí ni con la base de datos real.
"""

import os
import secrets
import tempfile
from pathlib import Path

import pytest

# Generamos una clave aleatoria para tests (nunca hardcodeada en el código)
os.environ["MASTER_ENCRYPTION_KEY"] = secrets.token_urlsafe(32)


@pytest.fixture(autouse=True)
def bd_temporal(tmp_path, monkeypatch):
    """
    Fixture que se ejecuta automáticamente en cada test.

    Crea una base de datos SQLite temporal y redirige DB_PATH a ella.
    Al finalizar el test, pytest borra el directorio temporal.

    `monkeypatch` permite modificar variables de módulos de forma segura
    y revertirlas automáticamente al terminar cada test.
    """
    import app.config as cfg
    import app.database as db

    db_path = tmp_path / "test_ciphie.db"

    # Redirigimos las rutas a la BD temporal
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)

    # Creamos las tablas en la BD temporal
    db.inicializar_bd()

    yield  # aquí se ejecuta el test

    # El directorio tmp_path se borra automáticamente al terminar
