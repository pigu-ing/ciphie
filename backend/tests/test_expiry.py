"""
tests/test_expiry.py — Tests para la feature de expiración de secretos.
"""

from datetime import datetime, timedelta

import pytest
from app.auth import registrar_usuario
from app.crypto import cifrar
from app.database import agregar_secreto, secretos_por_vencer, secretos_vencidos


def _usuario(username="alice"):
    return registrar_usuario(username, f"{username}@test.com", "password12345", "frase")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class TestSecretosVencidos:
    def test_secreto_sin_expiry_no_aparece_como_vencido(self):
        u = _usuario()
        agregar_secreto("clave", cifrar("valor"), u.id, expires_at=None)
        assert secretos_vencidos(u.id) == []

    def test_secreto_con_expiry_pasado_esta_vencido(self):
        u = _usuario()
        ayer = _iso(datetime.now() - timedelta(days=1))
        s = agregar_secreto("clave", cifrar("valor"), u.id, expires_at=ayer)
        vencidos = secretos_vencidos(u.id)
        assert len(vencidos) == 1
        assert vencidos[0].id == s.id

    def test_secreto_con_expiry_futuro_no_esta_vencido(self):
        u = _usuario()
        manana = _iso(datetime.now() + timedelta(days=1))
        agregar_secreto("clave", cifrar("valor"), u.id, expires_at=manana)
        assert secretos_vencidos(u.id) == []

    def test_solo_devuelve_vencidos_del_usuario(self):
        u1 = _usuario("alice")
        u2 = _usuario("bob")
        ayer = _iso(datetime.now() - timedelta(days=1))
        agregar_secreto("clave_alice", cifrar("v"), u1.id, expires_at=ayer)
        agregar_secreto("clave_bob",   cifrar("v"), u2.id, expires_at=ayer)
        assert len(secretos_vencidos(u1.id)) == 1
        assert secretos_vencidos(u1.id)[0].name == "clave_alice"

    def test_multiples_vencidos(self):
        u = _usuario()
        hace_dias = _iso(datetime.now() - timedelta(days=10))
        agregar_secreto("s1", cifrar("v"), u.id, expires_at=hace_dias)
        agregar_secreto("s2", cifrar("v"), u.id, expires_at=hace_dias)
        agregar_secreto("s3", cifrar("v"), u.id, expires_at=None)
        vencidos = secretos_vencidos(u.id)
        assert len(vencidos) == 2
        nombres = {s.name for s in vencidos}
        assert nombres == {"s1", "s2"}


class TestSecretosPorVencer:
    def test_secreto_sin_expiry_no_aparece(self):
        u = _usuario()
        agregar_secreto("clave", cifrar("v"), u.id, expires_at=None)
        assert secretos_por_vencer(u.id) == []

    def test_secreto_que_vence_en_menos_de_7_dias_aparece(self):
        u = _usuario()
        en_3_dias = _iso(datetime.now() + timedelta(days=3))
        s = agregar_secreto("clave", cifrar("v"), u.id, expires_at=en_3_dias)
        por_vencer = secretos_por_vencer(u.id, dias=7)
        assert len(por_vencer) == 1
        assert por_vencer[0].id == s.id

    def test_secreto_que_vence_despues_del_umbral_no_aparece(self):
        u = _usuario()
        en_30_dias = _iso(datetime.now() + timedelta(days=30))
        agregar_secreto("clave", cifrar("v"), u.id, expires_at=en_30_dias)
        assert secretos_por_vencer(u.id, dias=7) == []

    def test_secreto_ya_vencido_no_aparece_en_por_vencer(self):
        u = _usuario()
        ayer = _iso(datetime.now() - timedelta(days=1))
        agregar_secreto("clave", cifrar("v"), u.id, expires_at=ayer)
        # Ya vencido no debe aparecer en "por vencer"
        assert secretos_por_vencer(u.id, dias=7) == []

    def test_umbral_personalizado(self):
        u = _usuario()
        en_20_dias = _iso(datetime.now() + timedelta(days=20))
        s = agregar_secreto("clave", cifrar("v"), u.id, expires_at=en_20_dias)
        assert secretos_por_vencer(u.id, dias=7)  == []
        assert len(secretos_por_vencer(u.id, dias=30)) == 1
        assert secretos_por_vencer(u.id, dias=30)[0].id == s.id

    def test_expires_at_se_guarda_y_recupera(self):
        u = _usuario()
        en_5_dias = _iso(datetime.now() + timedelta(days=5))
        s = agregar_secreto("clave", cifrar("v"), u.id, expires_at=en_5_dias)
        assert s.expires_at is not None
        assert s.expires_at.startswith(en_5_dias[:10])  # mismo día
