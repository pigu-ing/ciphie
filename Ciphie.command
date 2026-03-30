#!/bin/bash
# =============================================================================
# Ciphie.command — Lanzador de escritorio para macOS
#
# Doble clic en este archivo para abrir Ciphie.
# macOS abrira una ventana de Terminal y ejecutara este script.
#
# La primera vez puede pedir confirmacion de seguridad:
#   "¿Deseas abrir Ciphie.command?" → clic en "Abrir"
# =============================================================================

# Ir al directorio donde está este archivo (la raíz del proyecto)
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "================================================"
echo "  Ciphie — Secrets Manager"
echo "================================================"
echo ""

# Añadir rutas comunes de uv y Homebrew al PATH
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Verificar que el entorno virtual existe y tiene Python 3.11+
VENV_OK=false
if [ -d ".venv" ]; then
    VENV_PY_VER=$(.venv/bin/python3 -c "import sys; print(sys.version_info[:2])" 2>/dev/null)
    if [[ "$VENV_PY_VER" == "(3, 11)"* || "$VENV_PY_VER" == "(3, 12)"* || "$VENV_PY_VER" == "(3, 13)"* ]]; then
        VENV_OK=true
    else
        echo "Entorno virtual existente usa Python incompatible ($VENV_PY_VER), recreando..."
        rm -rf .venv
    fi
fi

if [ "$VENV_OK" = false ]; then
    # Buscar Python 3.11+ con Tkinter (preferir Homebrew sobre uv)
    PYTHON_WITH_TK=""
    for candidate in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /usr/local/bin/python3.14 /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11; do
        if [ -x "$candidate" ] && "$candidate" -c "import tkinter" 2>/dev/null; then
            PYTHON_WITH_TK="$candidate"
            break
        fi
    done

    if [ -n "$PYTHON_WITH_TK" ]; then
        echo "Creando entorno virtual con $PYTHON_WITH_TK..."
        "$PYTHON_WITH_TK" -m venv .venv
    elif command -v uv &> /dev/null; then
        echo "Creando entorno virtual con uv (Python 3.11)..."
        uv venv .venv --python 3.11
    else
        echo "[ERROR] No se encontro Python 3.11+ con Tkinter."
        echo "Instala Python con: brew install python-tk@3.14"
        read -rp "Presiona Enter para cerrar..."
        exit 1
    fi
    echo ""
fi

# Activar el entorno virtual
source .venv/bin/activate

# Verificar que el comando ciphie está instalado
if ! command -v ciphie &> /dev/null; then
    echo "Instalando Ciphie por primera vez..."
    if command -v uv &> /dev/null; then
        uv pip install -r requirements.txt -q
        uv pip install -e . -q
    else
        pip install --upgrade pip -q
        pip install -r requirements.txt -q
        pip install -e . -q
    fi
    if ! command -v ciphie &> /dev/null; then
        echo "[ERROR] La instalacion fallo. Revisa los mensajes anteriores."
        read -rp "Presiona Enter para cerrar..."
        exit 1
    fi
    echo "Listo."
    echo ""
fi

# Verificar que existe el .env
if [ ! -f ".env" ]; then
    echo "[ERROR] No se encontro el archivo .env"
    echo ""
    echo "Crea uno a partir del ejemplo:"
    echo "  cp .env.example .env"
    echo ""
    echo "Luego edita .env y rellena los valores reales."
    echo ""
    read -rp "Presiona Enter para cerrar..."
    exit 1
fi

# Iniciar Ciphie
ciphie start

# Mantener la ventana de terminal abierta para ver posibles errores
echo ""
read -rp "Presiona Enter para cerrar esta ventana..."
