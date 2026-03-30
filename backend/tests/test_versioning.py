"""
tests/test_versioning.py — Tests para la feature de versionado de secretos.
"""

import pytest
from app.auth import registrar_usuario
from app.crypto import cifrar, descifrar
from app.database import (
    agregar_secreto,
    editar_secreto,
    listar_versiones,
    obtener_secreto,
    restaurar_version,
)


def _usuario(username="alice"):
    return registrar_usuario(username, f"{username}@test.com", "password12345", "frase")


class TestEditarSecreto:
    def test_editar_actualiza_el_valor(self):
        u = _usuario()
        s = agregar_secreto("api_key", cifrar("valor_original"), u.id)
        editar_secreto(s.id, u.id, cifrar("valor_nuevo"), "api_key", "api key")
        actualizado = obtener_secreto(s.id, u.id)
        assert descifrar(actualizado.encrypted_value) == "valor_nuevo"

    def test_editar_actualiza_nombre_y_categoria(self):
        u = _usuario()
        s = agregar_secreto("viejo_nombre", cifrar("valor"), u.id, "otro")
        editar_secreto(s.id, u.id, cifrar("valor"), "nuevo_nombre", "token")
        actualizado = obtener_secreto(s.id, u.id)
        assert actualizado.name == "nuevo_nombre"
        assert actualizado.category == "token"

    def test_editar_secreto_inexistente_devuelve_false(self):
        u = _usuario()
        resultado = editar_secreto(9999, u.id, cifrar("x"), "nombre", "otro")
        assert resultado is False

    def test_no_puede_editar_secreto_de_otro_usuario(self):
        u1 = _usuario("alice")
        u2 = _usuario("bob")
        s = agregar_secreto("clave", cifrar("original"), u1.id)
        resultado = editar_secreto(s.id, u2.id, cifrar("robado"), "clave", "otro")
        assert resultado is False
        # El valor original no cambió
        assert descifrar(obtener_secreto(s.id, u1.id).encrypted_value) == "original"


class TestVersionado:
    def test_editar_guarda_version_anterior(self):
        u = _usuario()
        s = agregar_secreto("token", cifrar("v1"), u.id)
        editar_secreto(s.id, u.id, cifrar("v2"), "token", "token")
        versiones = listar_versiones(s.id, u.id)
        assert len(versiones) == 1
        assert descifrar(versiones[0].encrypted_value) == "v1"

    def test_multiples_ediciones_acumulan_versiones(self):
        u = _usuario()
        s = agregar_secreto("pass", cifrar("v1"), u.id)
        editar_secreto(s.id, u.id, cifrar("v2"), "pass", "contrasena")
        editar_secreto(s.id, u.id, cifrar("v3"), "pass", "contrasena")
        editar_secreto(s.id, u.id, cifrar("v4"), "pass", "contrasena")
        versiones = listar_versiones(s.id, u.id)
        assert len(versiones) == 3
        # Más reciente primero (v3, v2, v1)
        valores = [descifrar(v.encrypted_value) for v in versiones]
        assert valores == ["v3", "v2", "v1"]

    def test_secreto_nuevo_no_tiene_versiones(self):
        u = _usuario()
        s = agregar_secreto("clave", cifrar("valor"), u.id)
        assert listar_versiones(s.id, u.id) == []

    def test_versiones_aisladas_por_secreto(self):
        u = _usuario()
        s1 = agregar_secreto("s1", cifrar("a1"), u.id)
        s2 = agregar_secreto("s2", cifrar("b1"), u.id)
        editar_secreto(s1.id, u.id, cifrar("a2"), "s1", "otro")
        assert len(listar_versiones(s1.id, u.id)) == 1
        assert len(listar_versiones(s2.id, u.id)) == 0

    def test_no_puede_ver_versiones_de_otro_usuario(self):
        u1 = _usuario("alice")
        u2 = _usuario("bob")
        s = agregar_secreto("clave", cifrar("v1"), u1.id)
        editar_secreto(s.id, u1.id, cifrar("v2"), "clave", "otro")
        # bob no puede ver versiones de alice
        assert listar_versiones(s.id, u2.id) == []


class TestRestaurarVersion:
    def test_restaurar_recupera_valor_anterior(self):
        u = _usuario()
        s = agregar_secreto("pass", cifrar("original"), u.id)
        editar_secreto(s.id, u.id, cifrar("modificado"), "pass", "contrasena")
        versiones = listar_versiones(s.id, u.id)
        restaurar_version(versiones[0].id, s.id, u.id)
        restaurado = obtener_secreto(s.id, u.id)
        assert descifrar(restaurado.encrypted_value) == "original"

    def test_restaurar_crea_nueva_version_del_valor_actual(self):
        """Restaurar es reversible: guarda el valor actual antes de restaurar."""
        u = _usuario()
        s = agregar_secreto("pass", cifrar("v1"), u.id)
        editar_secreto(s.id, u.id, cifrar("v2"), "pass", "contrasena")
        versiones_antes = listar_versiones(s.id, u.id)
        restaurar_version(versiones_antes[0].id, s.id, u.id)
        versiones_despues = listar_versiones(s.id, u.id)
        # Hay una versión más (v2 quedó guardada)
        assert len(versiones_despues) == len(versiones_antes) + 1

    def test_restaurar_version_inexistente_devuelve_false(self):
        u = _usuario()
        s = agregar_secreto("pass", cifrar("v1"), u.id)
        assert restaurar_version(9999, s.id, u.id) is False

    def test_no_puede_restaurar_version_de_otro_usuario(self):
        u1 = _usuario("alice")
        u2 = _usuario("bob")
        s = agregar_secreto("pass", cifrar("v1"), u1.id)
        editar_secreto(s.id, u1.id, cifrar("v2"), "pass", "contrasena")
        ver = listar_versiones(s.id, u1.id)[0]
        assert restaurar_version(ver.id, s.id, u2.id) is False
