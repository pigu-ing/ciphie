# Changelog

Todos los cambios notables de este proyecto se documentan aquí.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

---

## [1.0.0] - 2026-03-31

### Added
- **Instalación con pip**: `pyproject.toml` completo con `pip install ciphie`. Dependencias opcionales: `ciphie[qr]` (QR TOTP), `ciphie[sms]` (Twilio), `ciphie[macos]` (Touch ID). Única dependencia obligatoria: `cryptography`.
- **Compatibilidad multiplataforma**: `ciphie start` funciona en Windows, macOS y Linux. El separador de PYTHONPATH usa `os.pathsep`; pyobjc solo se instala en macOS.
- **Directorio de configuración portátil**: `config.py` resuelve automáticamente la ruta de `.env` y `ciphie.db` — directorio actual en modo dev, `~/.ciphie/` tras `pip install`. Configurable via `CIPHIE_HOME`.
- **Internacionalización completa**: nombres de categorías y campos del formulario ahora se traducen al cambiar de idioma. Funciones `TC()`, `TF()`, `_cat_key()` en el frontend.
- **Auditoría de accesos**: tabla `audit_log`; vista "📋 actividad" con entradas color-coded.
- **Versionado de secretos**: tabla `secret_versions`; historial por secreto con botón "restaurar" reversible.
- **Expiración de secretos**: columna `expires_at`; íconos ⚠️/🔴 y banner de alerta. Dropdown con opciones 30/60/90 días o fecha personalizada.
- **Edición de secretos**: menú ⋮ con ver, copiar, editar, historial, eliminar.
- **Campos por categoría**: formularios dinámicos con plantillas (`PLANTILLAS_CAMPOS`). Categorías: `contrasena`, `tarjeta`, `api key`, `token`, `nota`, `env`, `otro`. Secretos serializados como JSON multi-campo.
- **2FA completo**: TOTP (app autenticadora), email OTP, SMS (Twilio), Touch ID (macOS). Método elegible en tiempo de login.
- **QR en setup TOTP**: modal de activación con QR (si `qrcode[pil]` instalado) o instrucciones manuales.
- **Cierre de sesión por inactividad**: 10 minutos sin actividad → vuelve al login.
- **CLI ampliado**: `ciphie secrets list/get/add` con autenticación interactiva y soporte 2FA.
- **Suite de tests**: 88 tests en verde cubriendo auth, 2FA, registro, secretos, versionado, auditoría, expiración y crypto.

### Security
- **TOTP secrets cifrados**: almacenados con AES-256-GCM (mismo mecanismo que el resto de secretos). Migración automática de registros en plaintext al inicializar.
- **Rate-limiting en login**: bloqueo de cuenta por 15 minutos tras 5 intentos fallidos. Columnas `failed_login_attempts` / `locked_until` con migración automática.
- **OTPs anti fuerza bruta**: invalidación automática tras 5 intentos fallidos; TTL de 5 minutos.
- **STARTTLS con verificación TLS**: `ssl.create_default_context()` en `_enviar_email()`, evitando MITM en el canal SMTP.
- **Permisos de BD**: `ciphie.db` creado con permisos `0o600` (solo propietario).
- **PBKDF2-HMAC-SHA256**: 310.000 iteraciones (recomendación OWASP 2023) para hashing de contraseñas.
- **Comparación en tiempo constante**: `hmac.compare_digest` en verificación de passwords y OTPs.

### Fixed
- `_calcular_expires_at()` lanza `ValueError` en lugar de retornar el sentinel `"error"`.
- `MouseWheel` en canvas: `unbind_all` antes de `bind_all` y en evento `<Destroy>`.
- `ALTER TABLE` en migraciones captura `sqlite3.OperationalError` específicamente.
- `_verify_password()` loguea excepciones en lugar de silenciarlas.
- Parser de `.env` elimina comentarios inline.
- `.env.example`: instrucción de generación de clave corregida (era Fernet).

### Removed
- Funciones legacy rotas de 2FA email: `generar_otp_email()`, `verificar_otp_email()`, `autenticar_paso2_email()`.

---

## [2026-03-30] — Campos estructurados, i18n, biometría y launcher

### Added
- **Campos por categoría** (`PLANTILLAS_CAMPOS`): formularios dinámicos según el tipo de secreto. Categorías: `contrasena`, `tarjeta`, `api key`, `token`, `nota`, `env`, `otro`. Los secretos se serializan como JSON multi-campo (`{"__type":"multi","campos":{...}}`).
- **Internacionalización**: soporte para español e inglés con cambio al vuelo desde la UI. Textos en un diccionario `TEXTOS` indexado por idioma; función `T(clave)` para lookup.
- **QR code en setup TOTP**: si `qrcode[pil]` está instalado, el modal de activación 2FA muestra el QR directamente en la ventana.
- **Touch ID / biometría**: método de 2FA `"biometrico"` vía subprocess que llama a macOS `LocalAuthentication`. Requiere `pyobjc`.
- **Cierre de sesión por inactividad**: temporizador de 10 minutos (`INACTIVITY_TIMEOUT_MS`) que vuelve a la pantalla de login al detectar inactividad.
- **`Ciphie.command`**: launcher macOS con activación automática del entorno virtual, detección de Python, e instalación de dependencias en primera ejecución. Corregidos problemas de compatibilidad con rutas con espacios y permisos de ejecución.
- CLI (`backend/app/cli.py`) ampliado: comandos `secrets list`, `secrets get`, `secrets add` con soporte interactivo. `ciphie start` lanza la GUI como subproceso.

### Changed
- Categoría `"contraseña"` renombrada a `"contrasena"` (sin tilde) para consistencia con el resto del código.
- Nuevas categorías agregadas: `tarjeta`, `env`.
- `_parsear_valor()` y `_serializar_campos()` como funciones de frontend para manejar el formato multi-campo.
- `requirements.txt` actualizado con dependencias opcionales documentadas.

---

## [2026-03-29] — Auditoría, versionado, expiración y rediseño UI

### Added
- **Auditoría de accesos**: tabla `audit_log` en SQLite; se registran las acciones crear, ver, copiar, editar, eliminar y restaurar con timestamp. Vista "📋 actividad" en el sidebar del dashboard con entradas color-coded.
- **Versionado de secretos**: tabla `secret_versions`; cada edición guarda el valor anterior automáticamente. Opción "historial" en el menú ⋮ de cada secreto con lista de versiones y botón "restaurar" por versión. Restaurar es reversible (guarda el valor actual antes de sobreescribir).
- **Expiración de secretos**: columna `expires_at` en la tabla `secrets`. Dropdown "expira en" en el formulario de nuevo secreto (nunca / 30 / 60 / 90 días / personalizada). Ícono ⚠️ para secretos que vencen en menos de 7 días, 🔴 para vencidos. Banner de alerta al inicio con botón "renovar" por cada secreto vencido.
- **Edición de secretos**: opción "editar" en el menú ⋮; permite cambiar nombre, categoría, valor y fecha de expiración. Llama a `editar_secreto()` que guarda versión anterior antes de sobreescribir.
- **Tests**: 29 tests nuevos cubriendo las 3 features (`test_audit.py`, `test_versioning.py`, `test_expiry.py`). Suite completa: 51 tests, todos en verde.

### Changed
- `agregar_secreto()` acepta parámetro opcional `expires_at`.
- `editar_secreto()` reemplaza al viejo flujo de eliminar+crear; guarda versión anterior en `secret_versions`.
- Menú contextual ⋮ expandido: ver, copiar, editar, historial, eliminar.
- Sidebar del dashboard: se añade entrada "📋 actividad" entre secretos y usuario.

---

<!-- Versiones futuras se añaden aquí siguiendo el mismo formato:

## [0.2.0] - YYYY-MM-DD

### Added
- Nuevas funcionalidades

### Changed
- Cambios en funcionalidades existentes

### Fixed
- Correcciones de bugs

### Removed
- Funcionalidades eliminadas

-->
