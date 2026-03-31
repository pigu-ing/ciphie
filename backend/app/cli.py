"""
app/cli.py — Interfaz de linea de comandos de Ciphie.

Uso:
  ciphie start                      → abre la aplicacion de escritorio
  ciphie secrets list               → lista secretos del usuario
  ciphie secrets get <nombre>       → muestra el valor de un secreto
  ciphie secrets add <nombre>       → agrega un nuevo secreto
"""

import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

# Asegurar que backend/ este en PYTHONPATH
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))


def _verificar_env() -> None:
    from app.config import PROJECT_ROOT, _ENV_FILE
    if not _ENV_FILE.exists():
        print("[ERROR] No se encontro el archivo .env")
        print()
        print(f"Crea el archivo de configuracion en: {PROJECT_ROOT}")
        print()
        print("  1. Copia el ejemplo:")
        print(f"       cp .env.example {_ENV_FILE}")
        print()
        print("  2. Genera una clave maestra:")
        print('       python -c "import secrets; print(secrets.token_urlsafe(32))"')
        print()
        print("  3. Pega la clave en .env como MASTER_ENCRYPTION_KEY=<clave>")
        sys.exit(1)


def _autenticar_cli() -> "tuple":
    """Pide credenciales por stdin y retorna (username, usuario_obj)."""
    from app.auth import autenticar_paso1, autenticar_paso2_totp, autenticar_paso2_generico
    from app.auth import generar_otp_2fa_email, generar_otp_2fa_phone

    username = input("usuario: ").strip()
    password = getpass.getpass("contrasena: ")

    estado, usuario = autenticar_paso1(username, password)
    if estado == "fallo":
        print("[ERROR] Usuario o contrasena incorrectos.")
        sys.exit(1)

    if estado == "2fa_requerido":
        print("Se requiere verificacion de 2 pasos.")
        from app.auth import get_metodos_2fa_disponibles, obtener_config_2fa
        metodos = get_metodos_2fa_disponibles(username)
        cfg = obtener_config_2fa(username)

        if "totp_app" in metodos:
            codigo = input("Codigo de tu app autenticadora: ").strip()
            usuario = autenticar_paso2_totp(username, codigo)
        elif "email" in metodos:
            try:
                generar_otp_2fa_email(username)
                print(f"Codigo enviado a {cfg['email']}")
            except Exception as e:
                print(f"[ERROR] {e}")
                sys.exit(1)
            codigo = input("Codigo recibido por email: ").strip()
            usuario = autenticar_paso2_generico(username, codigo)
        elif "phone" in metodos:
            try:
                generar_otp_2fa_phone(username)
                print("Codigo enviado por SMS")
            except Exception as e:
                print(f"[ERROR] {e}")
                sys.exit(1)
            codigo = input("Codigo recibido por SMS: ").strip()
            usuario = autenticar_paso2_generico(username, codigo)
        else:
            print("[ERROR] No hay metodos de 2FA disponibles en CLI.")
            sys.exit(1)

        if usuario is None:
            print("[ERROR] Codigo incorrecto o expirado.")
            sys.exit(1)

    return username, usuario


def cmd_start(args: argparse.Namespace) -> None:
    _verificar_env()
    print("Iniciando Ciphie...")
    try:
        # Modo instalado (pip install ciphie): frontend es un paquete Python
        import frontend.app as gui
        gui.main()
    except ImportError:
        # Fallback modo desarrollo: ejecutar frontend/app.py como script
        project_root = Path(__file__).resolve().parent.parent.parent
        frontend_path = project_root / "frontend" / "app.py"
        if not frontend_path.exists():
            print(f"[ERROR] No se encontro el frontend en: {frontend_path}")
            sys.exit(1)
        env = os.environ.copy()
        backend_dir = str(project_root / "backend")
        sep = ";" if sys.platform == "win32" else ":"
        env["PYTHONPATH"] = backend_dir + (sep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        resultado = subprocess.run([sys.executable, str(frontend_path)], env=env,
                                   cwd=str(project_root))
        sys.exit(resultado.returncode)


def cmd_secrets_list(args: argparse.Namespace) -> None:
    """Lista los secretos del usuario."""
    _verificar_env()

    from app.database import inicializar_bd, listar_secretos
    inicializar_bd()

    _, usuario = _autenticar_cli()
    secretos = listar_secretos(usuario.id)

    if not secretos:
        print("(no hay secretos guardados)")
        return

    print(f"\n{'ID':>4}  {'NOMBRE':<30}  {'CATEGORIA':<12}  {'EXPIRA'}")
    print("-" * 70)
    for s in secretos:
        expira = s.expires_at[:10] if s.expires_at else "nunca"
        print(f"{s.id:>4}  {s.name:<30}  {s.category:<12}  {expira}")


def cmd_secrets_get(args: argparse.Namespace) -> None:
    """Muestra el valor de un secreto por nombre."""
    _verificar_env()

    from app.database import inicializar_bd, listar_secretos
    from app.crypto import descifrar
    import json

    inicializar_bd()
    _, usuario = _autenticar_cli()

    secretos = listar_secretos(usuario.id)
    nombre_buscado = args.nombre.lower()
    encontrado = next((s for s in secretos if s.name.lower() == nombre_buscado), None)
    if encontrado is None:
        # Busqueda parcial
        candidatos = [s for s in secretos if nombre_buscado in s.name.lower()]
        if not candidatos:
            print(f"[ERROR] Secreto '{args.nombre}' no encontrado.")
            sys.exit(1)
        if len(candidatos) == 1:
            encontrado = candidatos[0]
        else:
            print(f"Multiples coincidencias:")
            for c in candidatos:
                print(f"  {c.id}: {c.name}")
            sys.exit(1)

    valor = descifrar(encontrado.encrypted_value)
    try:
        data = json.loads(valor)
        if isinstance(data, dict) and data.get("__type") == "multi":
            print(f"\n[ {encontrado.name} ] ({encontrado.category})")
            print("-" * 40)
            for k, v in data.get("campos", {}).items():
                print(f"  {k}: {v}")
            return
    except Exception:
        pass
    print(f"\n[ {encontrado.name} ] ({encontrado.category})")
    print(f"  valor: {valor}")


def cmd_secrets_add(args: argparse.Namespace) -> None:
    """Agrega un nuevo secreto."""
    _verificar_env()

    from app.database import inicializar_bd, agregar_secreto, registrar_auditoria
    from app.crypto import cifrar
    import json

    inicializar_bd()
    _, usuario = _autenticar_cli()

    nombre = args.nombre
    categoria = args.categoria or "otro"
    valor = args.valor or getpass.getpass(f"valor para '{nombre}': ")

    datos = json.dumps({"__type": "multi", "campos": {"valor": valor}}, ensure_ascii=False)
    agregar_secreto(nombre, cifrar(datos), usuario.id, categoria)
    registrar_auditoria(usuario.id, "crear", nombre)
    print(f"[OK] Secreto '{nombre}' guardado correctamente.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ciphie",
        description="Ciphie — Secrets Manager opensource",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ciphie start
    start = subparsers.add_parser("start", help="Abre la aplicacion de escritorio")
    start.set_defaults(func=cmd_start)

    # ciphie secrets
    sec = subparsers.add_parser("secrets", help="Gestion de secretos via CLI")
    sec_sub = sec.add_subparsers(dest="secrets_cmd", required=True)

    # ciphie secrets list
    s_list = sec_sub.add_parser("list", help="Lista tus secretos")
    s_list.set_defaults(func=cmd_secrets_list)

    # ciphie secrets get <nombre>
    s_get = sec_sub.add_parser("get", help="Muestra el valor de un secreto")
    s_get.add_argument("nombre", help="Nombre del secreto")
    s_get.set_defaults(func=cmd_secrets_get)

    # ciphie secrets add <nombre>
    s_add = sec_sub.add_parser("add", help="Agrega un nuevo secreto")
    s_add.add_argument("nombre", help="Nombre del secreto")
    s_add.add_argument("--valor", "-v", help="Valor (si no se provee, se pide interactivamente)")
    s_add.add_argument("--categoria", "-c", default="otro",
                       choices=["contrasena", "tarjeta", "api key", "token", "nota", "env", "otro"],
                       help="Categoria del secreto (default: otro)")
    s_add.set_defaults(func=cmd_secrets_add)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
