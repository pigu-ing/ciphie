# Diario de desarrollo — Ciphie

Registro personal del progreso, decisiones y aprendizajes durante la construcción del proyecto.

---

## Plantilla de entrada

```
## [YYYY-MM-DD]

### Qué hice hoy
-

### Qué aprendí
-

### Problemas encontrados
-

### Cómo los resolví
-

### Próximos pasos
-
```

---

## [2026-04-03]

### Qué hice hoy
- **UI/UX**: corregí el ícono de la app en macOS — ahora usa `AppKit.NSApplication.setApplicationIconImage_` para que aparezca correctamente en el dock; fallback a `iconphoto` (PIL) si AppKit no está disponible. Separé el import de PIL del de `qrcode` para que el ícono funcione independientemente del soporte QR.
- **Sidebar**: revertí el cambio que había puesto la imagen del logo donde antes decía "ciphie" — el texto vuelve a mostrarse siempre.
- **Menú lateral**: moví "👤 usuario" para que quede justo debajo de "🏠 inicio".
- **Cierre automático configurable**: agregué un selector en Perfil → Sesión para que el usuario elija el tiempo de inactividad (30 s, 1 min, 1 min 30 s … hasta 5 min). Se aplica inmediatamente sin reiniciar sesión.
- **Bug crítico de tests**: corregí un leak de file descriptors en `database.py`. `get_connection()` devolvía un `sqlite3.Connection` y los callers lo usaban con `with conn:`, que en Python solo hace commit/rollback pero **no cierra la conexión**. Tras ~80 tests el proceso superaba el límite del OS (~256 FDs) y `test_expiry.py` fallaba con `OSError: Too many open files`. Fix: convertí `get_connection()` a `@contextmanager` que cierra la conexión en el `finally`.
- **Seguridad — bloqueo de cuenta**: reducí el límite de intentos de login de 5 a **3**; bajé el tiempo de bloqueo por defecto de 15 a **5 minutos**. Al bloquearse la cuenta se envía automáticamente un email de alerta al dueño con la hora de desbloqueo (silencioso si SMTP no configurado).
- **Bloqueo configurable por usuario**: agregué columna `lockout_minutes` en la tabla `users` (ALTER TABLE, default 5, compatible con usuarios existentes) y la función `set_lockout_minutes()` en `auth.py`. Desde Perfil → Seguridad el usuario puede elegir entre 5, 10, 15, 30 o 60 minutos.
- **Frontend**: el estado `"bloqueado"` que devuelve `autenticar_paso1()` ahora muestra un modal de error descriptivo en la pantalla de login (antes se ignoraba silenciosamente).
- Actualicé `README.md` y `CHANGELOG.md` con todos los cambios.

### Qué aprendí
- `with sqlite3.Connection` **no cierra la conexión** — solo gestiona la transacción (commit/rollback). Para cerrar hay que llamar `conn.close()` explícitamente o usar un `@contextmanager` propio. En CPython los objetos se cierran al garbage-collectarse, pero con muchos tests en el mismo proceso el GC no siempre corre a tiempo.
- `AppKit.NSApplication.setApplicationIconImage_` es la forma correcta de cambiar el ícono del dock en macOS desde Python. `iconphoto()` de Tkinter funciona en Linux/Windows pero no cambia el dock en macOS.
- Separar imports opcionales por funcionalidad (PIL para imágenes, qrcode para QR) es mejor que tener una sola flag `_QR_OK` que bloquee features independientes.

### Problemas encontrados
- El test `test_contador_se_resetea_en_login_exitoso` usaba exactamente 3 intentos fallidos seguidos de uno correcto — eso pasaba con el límite anterior de 5, pero con el nuevo límite de 3 el tercer intento ya bloqueaba la cuenta.
- El estado `"bloqueado"` devuelto por `autenticar_paso1()` no tenía manejo en el frontend: el `if/elif` no cubría ese caso y el login simplemente no hacía nada visible para el usuario.

### Cómo los resolví
- Reduje el test de contador a 2 intentos fallidos (por debajo del nuevo límite de 3).
- Agregué el `elif estado == "bloqueado"` antes del `elif estado == "fallo"` en `PantallaLogin._login()`.

### Próximos pasos
- [ ] Capturas de pantalla reales en `docs/screenshots/`
- [ ] Publicar en PyPI
- [ ] Notificaciones proactivas cuando un secreto está por vencer
- [ ] Búsqueda/filtro en la lista de secretos

---

## [2026-03-31] — continuación (release v1.0.0)

### Qué hice hoy (segunda sesión)
- Internacionalización completa del frontend: las categorías (`contrasena`, `tarjeta`, etc.) y los campos (`usuario`, `contrasena`, `url`, etc.) ahora se traducen al idioma activo. Agregué `TC()`, `TF()` y `_cat_key()` como helpers. Los StringVars de los OptionMenus guardan el nombre traducido y `_cat_key()` lo convierte de vuelta al key interno al guardar.
- Cierre de v1.0.0: `pyproject.toml` actualizado a v1.0.0 con `pip install ciphie` funcional. Dependencias opcionales: `ciphie[qr]` (QR TOTP), `ciphie[sms]` (Twilio), `ciphie[macos]` (Touch ID). pyobjc con guard `sys_platform == 'darwin'` para que no se instale en Windows ni Linux.
- `frontend/__init__.py` creado para que `frontend/` sea un paquete Python instalable.
- `config.py` refactorizado: `_find_project_root()` resuelve la ruta de `.env` y `ciphie.db` según el contexto — directorio actual si hay `.env` (modo dev), `~/.ciphie/` si no (modo pip install), o `CIPHIE_HOME` si está definido.
- `cli.py`: `cmd_start` ahora llama `frontend.app.main()` directamente en lugar de un subprocess, lo que funciona correctamente después de `pip install`. Fallback a subprocess si el import falla. `_verificar_env()` ya no recibe `project_root` como parámetro. Separador de PYTHONPATH usa `os.pathsep` (compatible con Windows).
- README actualizado: badge de versión, sección "Capturas de pantalla" con placeholders, sección "Primeros pasos" con los 4 pasos desde cero, instrucciones de `pip install` con extras.
- CHANGELOG: `[Unreleased]` movido a `[1.0.0] - 2026-03-31`.

### Qué aprendí
- En `pyproject.toml` con setuptools, se pueden tener paquetes en directorios distintos usando `[tool.setuptools.package-dir]` con mapeo explícito (`"app" = "backend/app"`, `"frontend" = "frontend"`). Más predecible que `packages.find` cuando la estructura no es estándar.
- Para dependencias opcionales en pyproject.toml, `sys_platform == 'darwin'` dentro del string de la dependencia es la forma correcta de hacerlas condicionales por OS. Funciona tanto en `[project.optional-dependencies]` como en `[project.dependencies]`.
- Cuando un CLI tool llama a `subprocess.run([sys.executable, "archivo.py"])`, eso funciona en modo dev pero falla tras pip install porque el archivo puede no estar donde se espera. La solución correcta es empaquetar el módulo e importarlo directamente.
- `PROJECT_ROOT` calculado a partir de `__file__` en `config.py` apunta al source tree en modo dev, pero a site-packages tras pip install. Necesita ser recalculado con lógica de "buscar el .env" para que funcione en ambos contextos.

### Problemas encontrados
- Al cambiar el OptionMenu de categorías para mostrar nombres traducidos, `_actualizar_campos_inicio()` recibía el nombre traducido ("password") como argumento y lo usaba como key en `PLANTILLAS_CAMPOS`, que solo tiene keys en español. Fallback a "otro" silenciosamente.
- `_find_project_root()` en tests: si el test se corre desde el directorio del proyecto y hay un `.env` real, `PROJECT_ROOT` apunta al proyecto. Pero los tests monkeypatchean `DB_PATH` directamente, así que no hay problema real.

### Cómo los resolví
- Agregué `_cat_key(display)` que hace el mapeo inverso: itera `CATEGORIAS`, compara `TC(cat) == display` y devuelve el key interno. Se aplica en `_actualizar_campos_inicio`, `_guardar_secreto` y `_guardar` del editor.
- Los tests no se vieron afectados porque monkeypatchean `DB_PATH` directamente, sin pasar por `_find_project_root()`.

### Próximos pasos
- [ ] Agregar capturas de pantalla reales en `docs/screenshots/`
- [ ] Publicar en PyPI
- [ ] Notificaciones proactivas cuando un secreto está por vencer
- [ ] Búsqueda/filtro en la lista de secretos

---

## [2026-03-31]

### Qué hice hoy
- Hice una auditoría general del proyecto e implementé todos los fixes resultantes: seguridad crítica, bugs de lógica y cobertura de tests.
- **Seguridad**: cifrado de TOTP secrets en BD (con migración automática al inicializar), rate-limiting en login (5 intentos → bloqueo 15 min, columnas `failed_login_attempts`/`locked_until`), invalidación de OTPs tras 5 fallos, STARTTLS con verificación TLS, chmod 0o600 en `ciphie.db`.
- **Bugs corregidos**: centinela `"error"` en `_calcular_expires_at` reemplazado por `raise ValueError`; `MouseWheel` en canvas ahora hace `unbind_all` antes del `bind_all` y al destruir el frame; `ALTER TABLE` captura `sqlite3.OperationalError` en lugar de `Exception`; parser de `.env` elimina comentarios inline.
- **Limpieza**: eliminadas las tres funciones legacy de 2FA email que estaban rotas (`autenticar_paso2_email`, etc.); corregida la instrucción de generación de clave en `.env.example` (era Fernet, ahora `secrets.token_urlsafe`).
- **Tests**: pasé de 51 a 88 tests. Cuatro archivos nuevos/ampliados: `test_2fa.py`, `test_secrets.py`, `test_registro.py`, y ampliación de `test_auth.py`. Suite en verde.

### Qué aprendí
- El HKDF salt fijo es una decisión de diseño aceptable siempre que la `MASTER_ENCRYPTION_KEY` sea única por instalación. Derivar una clave por usuario requeriría un campo adicional en la BD y más complejidad de rotación.
- Las funciones legacy pueden ser más peligrosas que útiles: `autenticar_paso2_email` usaba el dict equivocado y nunca podría haber verificado un OTP correctamente, pero su presencia daba falsa sensación de cobertura.
- En Python, usar excepciones como señales de control de flujo (en lugar de sentinel strings) es más robusto y pythónico; el stack trace es gratis y los callers no pueden confundir `None`-de-error con `None`-válido.

### Problemas encontrados
- La migración de TOTP secrets en `inicializar_bd()` requería importar desde `crypto.py`. Funciona sin circular import porque `database.py` → `config.py` y `crypto.py` → `config.py`, pero el import se hace dentro de la función para dejarlo explícito.
- Los tests de `test_registro.py` necesitan acceder al OTP guardado en `_otp_registro_pendientes` directamente (dict de módulo). La entrada es una tupla `(codigo, expira_en)`, no solo el código — hay que acceder como `_otp_registro_pendientes.get("alice")[0]`.

### Cómo los resolví
- Import condicional de `cifrar`/`descifrar` dentro de `inicializar_bd()`, envuelto en `try/except` para el caso en que `MASTER_ENCRYPTION_KEY` no esté configurada (p.ej. en entornos de CI sin `.env`).
- Test de OTP registro: uso `_guardar_otp` para capturar el código retornado directamente en lugar de leer el dict.

### Próximos pasos
- [ ] Remover `ciphie.db` del tracking de git (`git rm --cached ciphie.db`)
- [ ] Notificaciones proactivas cuando un secreto está por vencer
- [ ] Búsqueda/filtro en la lista de secretos
- [ ] Exportar/importar secretos cifrados

---

## [2026-03-29]

### Qué hice hoy
- Implementé 3 features nuevas en Ciphie: auditoría de accesos, versionado de secretos y expiración automática de credenciales.
- Reescribí `database.py` anadiendo las tablas `audit_log` y `secret_versions`, la columna `expires_at` en `secrets` (con migración automática via `ALTER TABLE` + try/except), nuevos dataclasses (`AuditEntry`, `SecretVersion`) y 7 funciones nuevas de CRUD.
- Actualicé `frontend/app.py`: sidebar con vista "📋 actividad", dropdown de expiración en el formulario de nuevo secreto, íconos ⚠️/🔴 en la lista, banner de secretos vencidos, opciones editar/historial en el menú ⋮, diálogos de edición y de historial con botón restaurar.
- Escribí 29 tests nuevos en 3 archivos (`test_audit.py`, `test_versioning.py`, `test_expiry.py`). Suite completa: 51 tests, todos en verde.

### Qué aprendí
- En SQLite, `ALTER TABLE ADD COLUMN` lanza excepción si la columna ya existe — envolverlo en try/except es el patrón correcto para migraciones sin romper bases de datos existentes.
- `restaurar_version()` debe guardar el valor actual antes de restaurar para que la operación sea reversible (el "restaurar" en sí se puede deshacer).
- En Tkinter/macOS, `tk.Label` con bindings es más confiable que `tk.Button` para respetar colores de fondo.

### Problemas encontrados
- El `Secreto` dataclass ya existía; anadir `expires_at` podía romper instancias creadas con `**dict(fila)` si la columna no estaba en todas las consultas.

### Cómo los resolví
- Anadí `expires_at` al final del dataclass con `= None` como default, y lo incluí en la constante `_COLS_SECRETO` usada por todas las consultas. Así todas las instancias reciben el campo y el código existente sigue funcionando sin cambios.

### Próximos pasos
- [ ] Implementar notificaciones proactivas (push/email) cuando un secreto está por vencer
- [ ] Agregar búsqueda/filtro en la lista de secretos
- [ ] Exportar/importar secretos cifrados

---

## [2026-03-30]

### Qué hice hoy
- Agregué soporte multi-campo para secretos: cada categoría tiene una plantilla de campos (`PLANTILLAS_CAMPOS`). Los valores se serializan como JSON `{"__type":"multi","campos":{...}}` antes de cifrar.
- Implementé internacionalización: diccionario `TEXTOS` con español e inglés, función `T(clave)`, selector de idioma en la UI con cambio al vuelo.
- Añadí soporte QR en el modal de activación TOTP (dependencia opcional `qrcode[pil]`).
- Implementé cierre de sesión automático por inactividad (10 min, via `after()` de Tkinter).
- Agregué método biométrico (Touch ID) como opción de 2FA en macOS via subprocess con `LocalAuthentication`.
- Amplié la CLI (`cli.py`): `secrets list`, `secrets get`, `secrets add` con lectura interactiva.
- Corregiía y expandí `Ciphie.command` (launcher macOS): detección de Python, activación de venv, instalación de deps en primera ejecución, manejo de rutas con espacios.

### Qué aprendí
- El patrón de serialización JSON para multi-campo permite agregar campos nuevos por categoría sin cambiar el esquema de la BD — todo cabe en `encrypted_value`.
- En Tkinter, `bind_all` es global a la aplicación; hay que recordar `unbind_all` al destruir el frame que lo registró.

### Problemas encontrados
- La categoría `"contraseña"` (con tilde) causaba problemas de comparación en algunos contextos.

### Cómo los resolví
- Renombré a `"contrasena"` (sin tilde) en todo el código y en los datos. Migración implícita: los secretos existentes con categoría `"contraseña"` simplemente se muestran sin color (caen en el fallback del diccionario).

### Próximos pasos
- [ ] Auditoría de seguridad del código
- [ ] Ampliar cobertura de tests a los flujos 2FA y registro con SMTP

---

## [2026-03-25]

### Qué hice hoy
- Creé la estructura inicial del proyecto Ciphie
- Configuré FastAPI con un endpoint básico de health check
- Definí las variables de entorno necesarias en `.env.example`
- Elegí el stack: FastAPI + SQLAlchemy + SQLite + Streamlit (más adelante)

### Qué aprendí
- FastAPI genera documentación interactiva automáticamente en `/docs`
- Las variables de entorno nunca deben hardcodearse; se cargan con `python-dotenv`
- Fernet (de la librería `cryptography`) usa AES-128 en modo CBC para cifrado simétrico

### Problemas encontrados
- Ninguno en esta sesión

### Próximos pasos
- [ ] Crear el modelo de base de datos para usuarios y secretos
- [ ] Configurar SQLAlchemy con SQLite
- [ ] Implementar hashing de contrasenas con passlib
- [ ] Crear endpoint de registro e inicio de sesión

---
