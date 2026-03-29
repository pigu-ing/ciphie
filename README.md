# Ciphie 🔐

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-WIP-orange)

**Ciphie** es un gestor de secretos local construido con Python puro.
Permite almacenar, recuperar y gestionar secretos cifrados (API keys, contraseñas, tokens)
de forma segura desde una aplicación de escritorio con interfaz estilo terminal.

---

## Features

- Cifrado **AES-256-GCM** con nonce aleatorio por cada secreto
- Derivación de clave segura con **HKDF-SHA256**
- Hashing de contraseñas con **PBKDF2-HMAC-SHA256** (310.000 iteraciones — OWASP 2023)
- Registro y autenticación de usuarios con protección contra timing attacks
- Aislamiento por usuario: cada secreto está vinculado a su propietario
- Base de datos **SQLite** local (sin servidor)
- Interfaz de escritorio **Tkinter** con tema oscuro estilo terminal
  - Botones grises (`#8b949e` exterior, `#21262d` interior) — sin botones blancos del sistema
  - Campos de contraseña con candado 🔒/🔓 para mostrar u ocultar el texto
- Registro con **verificación de cuenta por código** enviado al email (y SMS si Twilio configurado)
- **2FA en el inicio de sesión** con elección de método al momento del login:
  - Email (código OTP)
  - Celular / SMS (requiere Twilio — ver `.env`)
  - App autenticadora TOTP (Google Authenticator, Authy)
  - Touch ID / huella digital (macOS — requiere `pyobjc`)
- Una sola dependencia obligatoria: `cryptography`

---

## Requisitos

- Python 3.9+
- pip

---

## Instalación

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
```

Edita `.env` y añade tu clave maestra de cifrado:

```
MASTER_ENCRYPTION_KEY=<clave aleatoria>
```

Para generar una clave segura:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Arranca la aplicación

```bash
ciphie start
```

O directamente:

```bash
python frontend/app.py
```

---

## Estructura del proyecto

```
ciphie/
├── backend/
│   ├── app/
│   │   ├── auth.py       # registro y autenticación de usuarios
│   │   ├── crypto.py     # cifrado/descifrado AES-256-GCM
│   │   ├── database.py   # operaciones SQLite
│   │   ├── config.py     # configuración y carga del .env
│   │   └── cli.py        # punto de entrada CLI
│   └── tests/            # pruebas automatizadas
├── frontend/
│   └── app.py            # interfaz de escritorio Tkinter
├── docs/
│   └── journal.md        # diario de desarrollo
├── .env.example
├── requirements.txt
└── CHANGELOG.md
```

---

## Tests

```bash
cd backend
python -m pytest tests/ -v
```

---

## Seguridad

| Componente | Implementación |
|---|---|
| Cifrado de secretos | AES-256-GCM (AESGCM) |
| Derivación de clave | HKDF-SHA256 |
| Hash de contraseñas | PBKDF2-HMAC-SHA256, 310k iteraciones |
| Comparación de hashes | `hmac.compare_digest` (tiempo constante) |
| Nonce | 12 bytes aleatorios por cifrado (`os.urandom`) |
| Aislamiento de datos | `owner_id` en cada secreto, verificado en todas las queries |

---

## Licencia

MIT © 2026
