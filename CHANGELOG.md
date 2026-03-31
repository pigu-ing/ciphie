# Changelog

Todos los cambios notables de este proyecto se documentan aquí.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto sigue [Semantic Versioning](https://semver.org/lang/es/).

---

## [Unreleased]

### Security
- **TOTP secrets cifrados**: los secretos de autenticador TOTP ahora se almacenan cifrados con AES-256-GCM en la BD (igual que el resto de secretos). Migración automática al inicializar si hay secretos en plaintext.
- **Rate-limiting en login**: bloqueo de cuenta por 15 minutos tras 5 intentos de contraseña fallidos. Columnas `failed_login_attempts` y `locked_until` en la tabla `users` (migración automática). `autenticar_paso1()` retorna `("bloqueado", None)` cuando aplica.
- **OTPs anti fuerza bruta**: los OTPs (registro y 2FA) se invalidan automáticamente tras 5 intentos fallidos de verificación.
- **STARTTLS con verificación TLS**: `_enviar_email()` ahora pasa `ssl.create_default_context()` a `starttls()`, evitando ataques MITM en el canal SMTP.
- **Permisos de BD**: `inicializar_bd()` aplica `chmod 0o600` al archivo `ciphie.db` después de crearlo.

### Fixed
- `_calcular_expires_at()` ya no retorna la cadena `"error"` como centinela; ahora lanza `ValueError` y el caller hace early return con `except ValueError`.
- `MouseWheel` en canvas: se llama `unbind_all` antes de cada `bind_all` y se desvincula en el evento `<Destroy>` para evitar acumulación de handlers al navegar entre vistas.
- `ALTER TABLE` en migraciones captura `sqlite3.OperationalError` específicamente en lugar de `Exception` genérico.
- `_verify_password()` loguea la excepción con `logging.warning` en lugar de silenciarla.
- Parser de `.env` elimina comentarios inline (`CLAVE=valor # comentario` ahora funciona correctamente).
- `.env.example`: corregida instrucción de generación de `MASTER_ENCRYPTION_KEY` (era Fernet, ahora `secrets.token_urlsafe(32)` que es lo que usa el código).

### Removed
- Funciones legacy de 2FA email: `generar_otp_email()`, `verificar_otp_email()`, `autenticar_paso2_email()` — estaban rotas (usaban el dict `_otp_email_pendientes` en lugar de `_otp_2fa_pendientes` donde se generan los códigos reales).

### Added (tests)
- `test_2fa.py`: 11 tests cubriendo activar/desactivar 2FA, cifrado de TOTP en BD, OTP email, invalidación por intentos.
- `test_secrets.py`: 8 tests cubriendo eliminación con cascada de versiones, ownership, restauración de versiones.
- `test_registro.py`: 6 tests cubriendo flujo con y sin SMTP (mockeando `_enviar_email`), verificación de OTP.
- `test_auth.py` ampliado: 10 tests nuevos para `autenticar_paso1`, rate-limiting, `_verify_password` con hash corrupto, `actualizar_usuario`.
- Suite completa: **88 tests**, todos en verde.

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
