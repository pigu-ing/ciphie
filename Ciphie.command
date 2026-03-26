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

# Verificar que existe el entorno virtual
if [ ! -d ".venv" ]; then
    echo "[ERROR] No se encontro el entorno virtual (.venv)"
    echo ""
    echo "Configura el proyecto ejecutando estos comandos:"
    echo ""
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo "  pip install -e ."
    echo "  cp .env.example .env"
    echo "  # edita .env con tus valores"
    echo ""
    read -rp "Presiona Enter para cerrar..."
    exit 1
fi

# Activar el entorno virtual
source .venv/bin/activate

# Verificar que el comando ciphie está instalado
if ! command -v ciphie &> /dev/null; then
    echo "Instalando Ciphie por primera vez..."
    pip install -e . -q
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
