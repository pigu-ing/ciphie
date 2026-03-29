"""
tests/test_auth.py — Tests para el módulo de autenticación.
"""

import pytest
from app.auth import autenticar_usuario, registrar_usuario


class TestRegistrarUsuario:
    def test_crea_usuario_correctamente(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        assert u.id is not None
        assert u.username == "alice"
        assert u.email == "alice@example.com"
        assert u.is_active is True

    def test_username_duplicado_lanza_error(self):
        registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        with pytest.raises(ValueError, match="usuario"):
            registrar_usuario("alice", "otra@example.com", "password12345", "mi frase secreta")

    def test_email_duplicado_lanza_error(self):
        registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        with pytest.raises(ValueError, match="email"):
            registrar_usuario("bob", "alice@example.com", "password12345", "mi frase secreta")

    def test_username_muy_corto_lanza_error(self):
        with pytest.raises(ValueError, match="3 caracteres"):
            registrar_usuario("ab", "a@b.com", "password12345", "frase")

    def test_username_con_espacios_lanza_error(self):
        with pytest.raises(ValueError):
            registrar_usuario("alice smith", "a@b.com", "password12345", "frase")

    def test_email_invalido_lanza_error(self):
        with pytest.raises(ValueError, match="email"):
            registrar_usuario("alice", "noesmail", "password12345", "frase")

    def test_password_corta_lanza_error(self):
        with pytest.raises(ValueError, match="12 caracteres"):
            registrar_usuario("alice", "a@b.com", "corta", "frase")

    def test_contraseña_no_se_guarda_en_plano(self):
        u = registrar_usuario("alice", "a@b.com", "password12345", "mi frase secreta")
        from app.database import get_connection
        with get_connection() as conn:
            fila = conn.execute(
                "SELECT hashed_password FROM users WHERE id = ?", (u.id,)
            ).fetchone()
        assert fila["hashed_password"] != "password12345"
        assert ":" in fila["hashed_password"]  # formato salt:hash


class TestAutenticarUsuario:
    def test_credenciales_correctas_devuelven_usuario(self):
        registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        u = autenticar_usuario("alice", "password12345")
        assert u is not None
        assert u.username == "alice"

    def test_contraseña_incorrecta_devuelve_none(self):
        registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        assert autenticar_usuario("alice", "wrongpassword") is None

    def test_usuario_inexistente_devuelve_none(self):
        assert autenticar_usuario("fantasma", "password12345") is None

    def test_fallo_no_revela_causa(self):
        """Contraseña incorrecta y usuario inexistente devuelven lo mismo (None)."""
        registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        assert autenticar_usuario("alice", "wrong") is None
        assert autenticar_usuario("noexiste", "password12345") is None
