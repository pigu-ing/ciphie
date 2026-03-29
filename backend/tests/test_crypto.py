"""
tests/test_crypto.py — Tests para el módulo de cifrado.
"""

import pytest
from app.crypto import cifrar, descifrar


class TestCifrar:
    def test_devuelve_string(self):
        assert isinstance(cifrar("mi secreto"), str)

    def test_resultado_no_es_texto_plano(self):
        assert cifrar("mi secreto") != "mi secreto"

    def test_dos_cifrados_del_mismo_valor_son_distintos(self):
        # AES-256-GCM incluye un nonce aleatorio: cada cifrado es diferente
        assert cifrar("mismo valor") != cifrar("mismo valor")


class TestDescifrar:
    def test_descifra_correctamente(self):
        original = "API_KEY_SUPER_SECRETA"
        assert descifrar(cifrar(original)) == original

    def test_descifra_cadena_vacia(self):
        assert descifrar(cifrar("")) == ""

    def test_valor_corrupto_lanza_error(self):
        with pytest.raises(ValueError, match="descifrar"):
            descifrar("esto-no-es-un-token-fernet-valido")

    def test_valor_modificado_lanza_error(self):
        cifrado = cifrar("secreto")
        # Modificar un carácter del token lo invalida
        modificado = cifrado[:-1] + ("A" if cifrado[-1] != "A" else "B")
        with pytest.raises(ValueError):
            descifrar(modificado)


class TestCifradoYBD:
    def test_flujo_completo_guardar_y_recuperar(self):
        """Simula guardar un secreto y recuperarlo desde la BD."""
        from app.auth import registrar_usuario
        from app.database import agregar_secreto, listar_secretos

        usuario = registrar_usuario("alice", "a@b.com", "password12345", "mi frase secreta")
        valor_original = "mi_api_key_secreta"

        agregar_secreto("API_KEY", cifrar(valor_original), usuario.id)

        secretos = listar_secretos(usuario.id)
        assert len(secretos) == 1
        assert secretos[0].name == "API_KEY"
        assert descifrar(secretos[0].encrypted_value) == valor_original
