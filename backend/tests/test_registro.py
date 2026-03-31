"""
tests/test_registro.py — Tests para el flujo de registro con y sin SMTP.
"""

import pytest
from unittest.mock import patch
from app.auth import (
    iniciar_registro,
    verificar_otp_registro_y_activar,
    _otp_registro_pendientes,
)
from app.database import get_connection


class TestIniciarRegistroSinSmtp:
    def test_sin_smtp_usuario_activo_inmediatamente(self):
        with patch("app.auth._smtp_configurado", return_value=False):
            username, needs_verification = iniciar_registro(
                "alice", "alice@example.com", "password12345", "frase"
            )
        assert username == "alice"
        assert needs_verification is False

        with get_connection() as conn:
            fila = conn.execute(
                "SELECT is_active FROM users WHERE username=?", ("alice",)
            ).fetchone()
        assert fila["is_active"] == 1

    def test_sin_smtp_retorna_false(self):
        with patch("app.auth._smtp_configurado", return_value=False):
            _, needs = iniciar_registro(
                "bob", "bob@example.com", "password12345", "frase"
            )
        assert needs is False


class TestIniciarRegistroConSmtp:
    def test_con_smtp_usuario_inactivo_y_needs_verification_true(self):
        with patch("app.auth._smtp_configurado", return_value=True), \
             patch("app.auth._enviar_email"):
            username, needs_verification = iniciar_registro(
                "alice", "alice@example.com", "password12345", "frase"
            )
        assert username == "alice"
        assert needs_verification is True

        with get_connection() as conn:
            fila = conn.execute(
                "SELECT is_active FROM users WHERE username=?", ("alice",)
            ).fetchone()
        assert fila["is_active"] == 0

    def test_con_smtp_envia_email(self):
        with patch("app.auth._smtp_configurado", return_value=True), \
             patch("app.auth._enviar_email") as mock_email:
            iniciar_registro("alice", "alice@example.com", "password12345", "frase")
        mock_email.assert_called_once()
        destinatario = mock_email.call_args[0][0]
        assert destinatario == "alice@example.com"


class TestVerificarOtpRegistro:
    def test_codigo_correcto_activa_usuario(self):
        _otp_registro_pendientes.clear()
        with patch("app.auth._smtp_configurado", return_value=True), \
             patch("app.auth._enviar_email"):
            iniciar_registro("alice", "alice@example.com", "password12345", "frase")

        codigo = list(_otp_registro_pendientes.get("alice", ["", 0]))[0]
        assert codigo  # OTP fue guardado

        usuario = verificar_otp_registro_y_activar("alice", codigo)
        assert usuario is not None
        assert usuario.username == "alice"
        assert usuario.is_active is True

        with get_connection() as conn:
            fila = conn.execute(
                "SELECT is_active FROM users WHERE username=?", ("alice",)
            ).fetchone()
        assert fila["is_active"] == 1

    def test_codigo_incorrecto_retorna_none(self):
        _otp_registro_pendientes.clear()
        with patch("app.auth._smtp_configurado", return_value=True), \
             patch("app.auth._enviar_email"):
            iniciar_registro("alice", "alice@example.com", "password12345", "frase")

        resultado = verificar_otp_registro_y_activar("alice", "000000")
        assert resultado is None

        with get_connection() as conn:
            fila = conn.execute(
                "SELECT is_active FROM users WHERE username=?", ("alice",)
            ).fetchone()
        assert fila["is_active"] == 0  # sigue inactivo
