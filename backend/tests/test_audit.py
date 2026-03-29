"""
tests/test_audit.py — Tests para la feature de auditoría de accesos.
"""

import pytest
from app.auth import registrar_usuario
from app.crypto import cifrar
from app.database import (
    agregar_secreto,
    eliminar_secreto,
    listar_auditoria,
    registrar_auditoria,
)


def _usuario(username="alice"):
    return registrar_usuario(username, f"{username}@test.com", "password12345", "frase")


class TestRegistrarAuditoria:
    def test_registra_entrada_correctamente(self):
        u = _usuario()
        registrar_auditoria(u.id, "crear", "mi_secreto")
        entradas = listar_auditoria(u.id)
        assert len(entradas) == 1
        assert entradas[0].action == "crear"
        assert entradas[0].secret_name == "mi_secreto"
        assert entradas[0].user_id == u.id

    def test_timestamp_no_esta_vacio(self):
        u = _usuario()
        registrar_auditoria(u.id, "ver", "api_key")
        entradas = listar_auditoria(u.id)
        assert entradas[0].timestamp is not None
        assert len(entradas[0].timestamp) > 0

    def test_multiples_acciones_se_registran(self):
        u = _usuario()
        for accion in ("crear", "ver", "copiar", "eliminar"):
            registrar_auditoria(u.id, accion, "secreto")
        entradas = listar_auditoria(u.id)
        assert len(entradas) == 4
        acciones = {e.action for e in entradas}
        assert acciones == {"crear", "ver", "copiar", "eliminar"}

    def test_orden_mas_reciente_primero(self):
        u = _usuario()
        registrar_auditoria(u.id, "crear",  "secreto_a")
        registrar_auditoria(u.id, "ver",    "secreto_b")
        registrar_auditoria(u.id, "copiar", "secreto_c")
        entradas = listar_auditoria(u.id)
        # El id más alto debe ir primero
        assert entradas[0].id > entradas[1].id > entradas[2].id

    def test_auditoria_aislada_por_usuario(self):
        u1 = _usuario("alice")
        u2 = _usuario("bob")
        registrar_auditoria(u1.id, "crear", "secreto_alice")
        registrar_auditoria(u2.id, "crear", "secreto_bob")
        assert len(listar_auditoria(u1.id)) == 1
        assert listar_auditoria(u1.id)[0].secret_name == "secreto_alice"
        assert len(listar_auditoria(u2.id)) == 1
        assert listar_auditoria(u2.id)[0].secret_name == "secreto_bob"

    def test_usuario_sin_actividad_devuelve_lista_vacia(self):
        u = _usuario()
        assert listar_auditoria(u.id) == []

    def test_limite_recorta_resultados(self):
        u = _usuario()
        for i in range(10):
            registrar_auditoria(u.id, "ver", f"secreto_{i}")
        assert len(listar_auditoria(u.id, limite=3)) == 3
