# Ciphie 🔐

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/version-1.0.0-blue)

**Ciphie** es un gestor de secretos local construido con Python puro.
Permite almacenar, recuperar y gestionar secretos cifrados (API keys, contraseñas, tokens)
de forma segura desde una aplicación de escritorio con interfaz estilo terminal.

---

## Capturas de pantalla

![Login](docs/screenshots/login.png)
![Dashboard](docs/screenshots/dashboard.png)
![2FA](docs/screenshots/2fa.png)

---

## Features

- Cifrado **AES-256-GCM** con nonce aleatorio por cada secreto
- Derivación de clave segura con **HKDF-SHA256**
- Hashing de contraseñas con **PBKDF2-HMAC-SHA256** (310.000 iteraciones — OWASP 2023)
- Registro y autenticación de usuarios con protección contra timing attacks
- Aislamiento por usuario: cada secreto está vinculado a su propietario
- Base de datos **SQLite** local (sin servidor)
- Interfaz de escritorio **Tkinter** con tema oscuro estilo terminal
  - Campos de contraseña con candado 🔒/🔓 para mostrar u ocultar el texto
- Registro con **verificación de cuenta por código** enviado al email (y SMS si Twilio configurado)
- **2FA en el inicio de sesión** con elección de método al momento del login:
  - App autenticadora TOTP (Google Authenticator, Authy) — secreto cifrado en BD
  - Touch ID / huella digital (macOS — requiere `pyobjc`)
- **Eliminación de cuenta** desde la pantalla de usuario, protegida por verificación 2FA si está activa; borra todos los secretos y datos del usuario en cascada
- **Campos por categoría** (plantillas dinámicas): `contrasena`, `tarjeta`, `api key`, `token`, `nota`, `env`, `otro`
- **Soporte QR** para onboarding TOTP (opcional — requiere `qrcode[pil]`)
- **Cierre de sesión automático** por inactividad, configurable entre 30 segundos y 5 minutos desde el perfil
- **Internacionalización**: interfaz en español e inglés con cambio al vuelo
- **Protección anti fuerza bruta**: bloqueo de cuenta tras 3 intentos fallidos; duración configurable por usuario (5 / 10 / 15 / 30 / 60 min, default 5 min); email de alerta al dueño de la cuenta al bloquearse
- Una sola dependencia obligatoria: `cryptography`

---

## Requisitos

- Python 3.11+
- pip

---

## Instalación

### Opción A — con pip (recomendado)

```bash
pip install ciphie
```

Dependencias opcionales:

```bash
pip install "ciphie[qr]"    # QR en setup de TOTP
pip install "ciphie[sms]"   # SMS via Twilio
pip install "ciphie[macos]" # Touch ID (solo macOS)
pip install "ciphie[all]"   # todo lo anterior
```

### Opción B — desde el código fuente

```bash
git clone https://github.com/tu-usuario/ciphie.git
cd ciphie
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
pip install -e .
```

---

## Primeros pasos

### 1. Crear el archivo de configuración

```bash
cp .env.example .env
```

> Si instalaste con `pip install ciphie`, crea el archivo en `~/.ciphie/.env`.

### 2. Generar y agregar la clave maestra

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Pegá el resultado en `.env`:

```
MASTER_ENCRYPTION_KEY=tu_clave_generada_aqui
```

### 3. Abrir la aplicación

```bash
ciphie start
```

### 4. Registrarse y crear el primer secreto

1. En la pantalla de login, hacé clic en **registrarse**
2. Completá usuario, email y contraseña (mínimo 12 caracteres)
3. Si configuraste SMTP en `.env`, verificá tu cuenta con el código que llegará al email
4. Una vez dentro, usá **➕ nuevo** en el sidebar para agregar tu primer secreto

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
│   ├── journal.md        # diario de desarrollo
│   └── screenshots/      # capturas de pantalla
├── .env.example
├── pyproject.toml
└── CHANGELOG.md
```

---

## Tests

```bash
python -m pytest backend/tests/ -v
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
| TOTP secrets | Cifrados con AES-256-GCM en la BD (igual que el resto de secretos) |
| Protección contra fuerza bruta | Bloqueo de cuenta tras 3 intentos fallidos; duración configurable por usuario (default 5 min); email de alerta al bloquearse |
| TLS / SMTP | STARTTLS con verificación de certificado (`ssl.create_default_context()`) |
| Permisos de BD | Archivo `ciphie.db` con permisos `0o600` (solo propietario) |

---

## Licencia

MIT © 2026
