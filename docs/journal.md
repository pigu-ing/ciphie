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
