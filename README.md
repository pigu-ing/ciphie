# Ciphie 🔐

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-WIP-orange)

**Ciphie** es un gestor de secretos opensource construido con Python.
Permite almacenar, recuperar y gestionar secretos cifrados (API keys, contraseñas, tokens)
de forma segura a través de una API REST.

---

## Features

- Almacenamiento cifrado de secretos con Fernet (AES-128)
- Autenticación con tokens JWT
- API REST documentada automáticamente con Swagger UI
- Base de datos SQLite para desarrollo, PostgreSQL-ready para producción
- Frontend en Streamlit (próximamente)

---

## Requisitos

- Python 3.11+
- pip

---

## Cómo correrlo

### 1. Clona el repositorio

```bash
git clone https://github.com/tu-usuario/ciphie.git
cd ciphie
```

### 2. Crea un entorno virtual e instala dependencias

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### 3. Configura las variables de entorno

```bash
cp .env.example .env
# Edita .env con tus valores reales
```

### 4. Arranca el servidor

```bash
uvicorn backend.app.main:app --reload
```

La API estará disponible en `http://localhost:8000`.
La documentación interactiva en `http://localhost:8000/docs`.

---

## Estructura del proyecto

```
ciphie/
├── backend/
│   ├── app/
│   │   ├── main.py       # punto de entrada de FastAPI
│   │   ├── models/       # modelos de base de datos (SQLAlchemy)
│   │   ├── routes/       # endpoints de la API
│   │   ├── services/     # lógica de negocio
│   │   └── core/         # configuración, seguridad, cifrado
│   └── tests/            # pruebas automatizadas
├── frontend/             # interfaz Streamlit (próximamente)
├── docs/
│   └── journal.md        # diario de desarrollo
├── .env.example
├── requirements.txt
└── CHANGELOG.md
```

---

## Licencia

MIT © 2026
