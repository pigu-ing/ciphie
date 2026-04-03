"""
tests/test_auth.py — Tests para el módulo de autenticación.
"""

import pytest
from app.auth import (
    autenticar_usuario,
    autenticar_paso1,
    registrar_usuario,
    actualizar_usuario,
    activar_2fa,
    generar_secreto_totp,
    _verify_password,
)


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

    def test_contrasena_no_se_guarda_en_plano(self):
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

    def test_contrasena_incorrecta_devuelve_none(self):
        registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        assert autenticar_usuario("alice", "wrongpassword") is None

    def test_usuario_inexistente_devuelve_none(self):
        assert autenticar_usuario("fantasma", "password12345") is None

    def test_fallo_no_revela_causa(self):
        """Contrasena incorrecta y usuario inexistente devuelven lo mismo (None)."""
        registrar_usuario("alice", "alice@example.com", "password12345", "mi frase secreta")
        assert autenticar_usuario("alice", "wrong") is None
        assert autenticar_usuario("noexiste", "password12345") is None


class TestAutenticarPaso1:
    def test_sin_2fa_retorna_ok(self):
        registrar_usuario("bob", "bob@example.com", "password12345", "frase bob")
        resultado, usuario = autenticar_paso1("bob", "password12345")
        assert resultado == "ok"
        assert usuario is not None
        assert usuario.username == "bob"

    def test_con_2fa_retorna_2fa_requerido(self):
        u = registrar_usuario("bob", "bob@example.com", "password12345", "frase bob")
        secreto = generar_secreto_totp()
        activar_2fa(u.id, "app", secreto)
        resultado, usuario = autenticar_paso1("bob", "password12345")
        assert resultado == "2fa_requerido"
        assert usuario is None

    def test_password_incorrecta_retorna_fallo(self):
        registrar_usuario("bob", "bob@example.com", "password12345", "frase bob")
        resultado, usuario = autenticar_paso1("bob", "wrongpassword")
        assert resultado == "fallo"
        assert usuario is None

    def test_usuario_inexistente_retorna_fallo(self):
        resultado, usuario = autenticar_paso1("nadie", "password12345")
        assert resultado == "fallo"
        assert usuario is None

    def test_bloqueo_tras_3_intentos_fallidos(self):
        registrar_usuario("bob", "bob@example.com", "password12345", "frase bob")
        for _ in range(3):
            autenticar_paso1("bob", "wrongpassword")
        resultado, _ = autenticar_paso1("bob", "password12345")
        assert resultado == "bloqueado"

    def test_contador_se_resetea_en_login_exitoso(self):
        registrar_usuario("bob", "bob@example.com", "password12345", "frase bob")
        for _ in range(2):  # menos del límite de bloqueo (3)
            autenticar_paso1("bob", "wrongpassword")
        resultado, usuario = autenticar_paso1("bob", "password12345")
        assert resultado == "ok"
        assert usuario is not None
        # Después del login exitoso, el contador debe estar en 0
        from app.database import get_connection
        with get_connection() as conn:
            fila = conn.execute(
                "SELECT failed_login_attempts FROM users WHERE username=?", ("bob",)
            ).fetchone()
        assert fila["failed_login_attempts"] == 0


class TestVerifyPassword:
    def test_hash_corrupto_devuelve_false_sin_raise(self):
        assert _verify_password("cualquiercosa", "hash_corrupto_sin_dos_puntos") is False

    def test_hash_con_bytes_no_hex_devuelve_false(self):
        assert _verify_password("pass", "gggg:zzzz") is False


class TestActualizarUsuario:
    def test_cambia_username(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        actualizar_usuario(u.id, new_username="alicia")
        u2 = autenticar_usuario("alicia", "password12345")
        assert u2 is not None
        assert u2.username == "alicia"

    def test_username_duplicado_lanza_error(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        registrar_usuario("bob", "bob@example.com", "password12345", "frase")
        with pytest.raises(ValueError, match="usuario"):
            actualizar_usuario(u.id, new_username="bob")

    def test_sin_cambios_no_lanza(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        actualizar_usuario(u.id)  # sin argumentos: no hace nada
