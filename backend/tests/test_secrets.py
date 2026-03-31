"""
tests/test_secrets.py — Tests para eliminación y restauración de secretos.
"""

import pytest
from app.auth import registrar_usuario
from app.database import (
    agregar_secreto,
    eliminar_secreto,
    get_connection,
    listar_secretos,
    listar_versiones,
    obtener_secreto,
    restaurar_version,
)
from app.crypto import cifrar


def _secreto_cifrado(texto="valor_de_prueba"):
    return cifrar(texto)


class TestEliminarSecreto:
    def test_elimina_secreto_correctamente(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        s = agregar_secreto("mi clave", _secreto_cifrado(), u.id)
        eliminar_secreto(s.id, u.id)
        assert obtener_secreto(s.id, u.id) is None

    def test_elimina_versiones_en_cascada(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        from app.database import editar_secreto
        s = agregar_secreto("mi clave", _secreto_cifrado("v1"), u.id)
        editar_secreto(s.id, u.id, _secreto_cifrado("v2"), "mi clave", "otro")
        eliminar_secreto(s.id, u.id)

        with get_connection() as conn:
            versiones = conn.execute(
                "SELECT id FROM secret_versions WHERE secret_id=?", (s.id,)
            ).fetchall()
        assert len(versiones) == 0

    def test_no_elimina_secreto_de_otro_usuario(self):
        u1 = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        u2 = registrar_usuario("bob", "bob@example.com", "password12345", "frase")
        s = agregar_secreto("mi clave", _secreto_cifrado(), u1.id)
        eliminar_secreto(s.id, u2.id)  # intento como otro usuario
        assert obtener_secreto(s.id, u1.id) is not None  # sigue existiendo

    def test_eliminar_inexistente_no_lanza(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        eliminar_secreto(9999, u.id)  # no debe lanzar excepción


class TestRestaurarVersion:
    def test_restaura_version_anterior(self):
        from app.database import editar_secreto
        from app.crypto import descifrar

        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        s = agregar_secreto("clave", _secreto_cifrado("v1"), u.id)
        editar_secreto(s.id, u.id, _secreto_cifrado("v2"), "clave", "otro")

        versiones = listar_versiones(s.id, u.id)
        assert len(versiones) == 1

        ok = restaurar_version(versiones[0].id, s.id, u.id)
        assert ok is True

        restaurado = obtener_secreto(s.id, u.id)
        assert descifrar(restaurado.encrypted_value) == "v1"

    def test_restaurar_guarda_valor_actual_como_version(self):
        from app.database import editar_secreto

        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        s = agregar_secreto("clave", _secreto_cifrado("v1"), u.id)
        editar_secreto(s.id, u.id, _secreto_cifrado("v2"), "clave", "otro")

        versiones_antes = listar_versiones(s.id, u.id)
        restaurar_version(versiones_antes[0].id, s.id, u.id)
        versiones_despues = listar_versiones(s.id, u.id)

        # Debe haber una versión extra (la v2 guardada antes del restore)
        assert len(versiones_despues) == len(versiones_antes) + 1

    def test_restaurar_version_de_otro_secreto_retorna_false(self):
        from app.database import editar_secreto

        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        s1 = agregar_secreto("s1", _secreto_cifrado("v1"), u.id)
        s2 = agregar_secreto("s2", _secreto_cifrado("v1"), u.id)
        editar_secreto(s1.id, u.id, _secreto_cifrado("v2"), "s1", "otro")

        versiones_s1 = listar_versiones(s1.id, u.id)
        # Intentar restaurar una versión de s1 en s2
        ok = restaurar_version(versiones_s1[0].id, s2.id, u.id)
        assert ok is False

    def test_restaurar_secreto_inexistente_retorna_false(self):
        u = registrar_usuario("alice", "alice@example.com", "password12345", "frase")
        assert restaurar_version(9999, 9999, u.id) is False
