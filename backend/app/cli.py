"""
app/cli.py — Interfaz de línea de comandos de Ciphie.

Uso:
  ciphie start            → abre la aplicación de escritorio
  ciphie start --no-gui   → solo verifica la configuración (útil para tests)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _verificar_env(project_root: Path) -> None:
    env_file = project_root / ".env"
    if not env_file.exists():
        print("[ERROR] No se encontro el archivo .env")
        print()
        print("Crea uno a partir del ejemplo:")
        print(f"  cp {project_root}/.env.example {project_root}/.env")
        print()
        print("Luego edita .env y rellena los valores reales.")
        sys.exit(1)


def cmd_start(args: argparse.Namespace) -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    _verificar_env(project_root)

    frontend = project_root / "frontend" / "app.py"
    if not frontend.exists():
        print(f"[ERROR] No se encontro el frontend en: {frontend}")
        sys.exit(1)

    # PYTHONPATH debe incluir backend/ para que `import app` funcione
    env = os.environ.copy()
    backend_dir = str(project_root / "backend")
    env["PYTHONPATH"] = backend_dir + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    print("Iniciando Ciphie...")

    # Ejecutamos el frontend en el mismo proceso de Python activo.
    # subprocess.run bloquea hasta que el usuario cierra la ventana.
    resultado = subprocess.run(
        [sys.executable, str(frontend)],
        env=env,
        cwd=str(project_root),
    )
    sys.exit(resultado.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ciphie",
        description="Ciphie — Secrets Manager opensource",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Abre la aplicación de escritorio")
    start.set_defaults(func=cmd_start)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
